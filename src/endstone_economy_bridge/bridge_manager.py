"""BridgeManager - the brain of EconomyBridge's two-way sync.

Responsibilities:
    - Listen to PlayerJoinEvent to reconcile balances on join.
    - Provide sync_player() / sync_all_online(), used by SyncTask
      (periodic scheduler) and on join.
    - Enforce the project's conflict rule:
        * If only ONE side differs from the last known synced baseline,
          that side legitimately changed (up OR down -- e.g. a shop
          purchase reducing a balance) and its value is pushed to the
          other side.
        * If BOTH sides differ from the baseline (a genuine simultaneous
          conflict -- e.g. a purchase on one side and a reward on the
          other, in the same sync cycle), both changes are treated as
          independent, legitimate transactions and merged additively:
              final = baseline + (coin - baseline) + (money - baseline)
          This is the same idea as merging two concurrent edits to a
          shared counter from a common ancestor (CRDT-style merge) -- it
          keeps BOTH transactions' effect, rather than arbitrarily
          discarding one of them the way a plain "highest wins" tie-break
          would.
        * The merged result is floored at 0 (a balance can never go
          negative, even if the summed deltas would otherwise imply it).
        * The very first reconciliation for a player (no baseline yet)
          has nothing to compute a delta against, so it falls back to
          "highest balance wins" just once, to establish the initial
          baseline.
"""
from endstone import Player
from endstone.event import PlayerJoinEvent, event_handler
from endstone.plugin import Plugin

from .config_manager import ConfigManager
from .providers.jweconomy_provider import JWEconomyProvider
from .providers.umoney_provider import UMoneyProvider
from .sync_state_store import SyncStateStore


class BridgeManager:
    def __init__(
        self,
        plugin: Plugin,
        config: ConfigManager,
        jweconomy: JWEconomyProvider,
        umoney: UMoneyProvider,
        state: SyncStateStore,
    ) -> None:
        self._plugin = plugin
        self._config = config
        self._jweconomy = jweconomy
        self._umoney = umoney
        self._state = state

    # ---- Event handler -------------------------------------------------
    @event_handler
    def on_player_join(self, event: PlayerJoinEvent) -> None:
        if not self._config.sync_on_join:
            return
        self.sync_player(event.player)

    # ---- Public API ------------------------------------------------------
    def sync_player(self, player: Player) -> None:
        """Reconcile one player's balance between JWEconomy and uMoney.

        Flow: fetch the Coin balance asynchronously (through JWEconomy's
        own event-loop) -> hop back onto the main server thread via the
        scheduler -> read uMoney's balance and decide there. Every write
        (to either plugin) and every read of uMoney/Player always happens
        on the main thread; only the JWEconomy read/write itself is async.
        """

        async def _fetch_coin() -> None:
            coin = await self._jweconomy.get_balance(player)
            if coin is None:
                return
            self._plugin.server.scheduler.run_task(
                self._plugin, lambda: self._reconcile(player, coin)
            )

        self._jweconomy.run_async(_fetch_coin())

    def sync_all_online(self) -> None:
        for player in self._plugin.server.online_players:
            self.sync_player(player)

    # ---- Internal ----------------------------------------------------------
    def _reconcile(self, player: Player, coin: int) -> None:
        money = self._umoney.get_balance(player)
        if money is None:
            return

        if coin == money:
            # Already in sync. Still (re)confirm the baseline in case this
            # is the very first time we've seen this player.
            self._state.set(player, coin)
            return

        baseline = self._state.get(player)

        if baseline is None:
            # No history at all -> nothing to compute a delta against.
            # Fall back to "highest wins" just this once, to establish
            # the initial baseline.
            final = max(coin, money)
            reason = "bootstrap (no baseline yet), highest wins"
        else:
            coin_changed = coin != baseline
            money_changed = money != baseline

            if coin_changed and not money_changed:
                final = coin
                reason = "JWEconomy"
            elif money_changed and not coin_changed:
                final = money
                reason = "uMoney"
            else:
                # Genuine conflict: both sides moved independently since
                # the last baseline. Merge both deltas additively instead
                # of discarding one side.
                delta_coin = coin - baseline
                delta_money = money - baseline
                final = max(0, baseline + delta_coin + delta_money)
                reason = (
                    f"merged conflict: baseline={baseline}, "
                    f"Δcoin={delta_coin:+d}, Δmoney={delta_money:+d}"
                )

        self._apply_final(player, final, coin, money, reason)

    def _apply_final(
        self, player: Player, final: int, coin: int, money: int, reason: str
    ) -> None:
        """Push `final` to whichever side(s) don't already hold it."""

        if money != final and not self._umoney.set_balance(player, final):
            return  # write failed; don't touch the baseline, retry next cycle

        if coin == final:
            self._finish(player, coin, money, final, reason)
            return

        async def _push_to_jweconomy() -> None:
            ok = await self._jweconomy.set_balance(player, final)
            if ok:
                self._plugin.server.scheduler.run_task(
                    self._plugin,
                    lambda: self._finish(player, coin, money, final, reason),
                )

        self._jweconomy.run_async(_push_to_jweconomy())

    def _finish(
        self, player: Player, coin: int, money: int, final: int, reason: str
    ) -> None:
        self._state.set(player, final)
        if self._config.debug:
            self._plugin.logger.info(
                f"[EconomyBridge] Sync {player.name} ({reason}): "
                f"coin={coin}, money={money} -> {final}"
            )
