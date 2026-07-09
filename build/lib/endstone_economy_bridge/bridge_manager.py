"""BridgeManager - otak sinkronisasi EconomyBridge.

Tanggung jawab:
    - Mendengarkan PlayerJoinEvent untuk sinkronisasi saat join.
    - Menyediakan sync_player() / sync_all_online() yang dipakai oleh
      SyncTask (scheduler berkala) maupun command /ecobridge sync.
    - Menjaga aturan inti proyek:
        1. Arah sinkronisasi SELALU JWEconomy -> uMoney, tidak pernah
           sebaliknya (JWEconomy adalah Source of Truth).
        2. Tidak melakukan update ke uMoney bila saldo sudah identik
           (menghindari pemanggilan API yang tidak perlu / spam).
"""
from endstone import Player
from endstone.event import PlayerJoinEvent, event_handler
from endstone.plugin import Plugin

from .config_manager import ConfigManager
from .providers.jweconomy_provider import JWEconomyProvider
from .providers.umoney_provider import UMoneyProvider


class BridgeManager:
    def __init__(
        self,
        plugin: Plugin,
        config: ConfigManager,
        source: JWEconomyProvider,
        target: UMoneyProvider,
    ) -> None:
        self._plugin = plugin
        self._config = config
        self._source = source
        self._target = target

    # ---- Event handler -------------------------------------------------
    @event_handler
    def on_player_join(self, event: PlayerJoinEvent) -> None:
        if not self._config.sync_on_join:
            return
        self.sync_player(event.player)

    # ---- Public API ------------------------------------------------------
    def sync_player(self, player: Player) -> None:
        """Sinkronkan satu player.

        Alur: ambil saldo JWEconomy secara async (lewat event-loop
        JWEconomy sendiri) -> lompat balik ke main thread server lewat
        scheduler -> baru sentuh API uMoney di sana. uMoney (dan objek
        Player) tidak thread-safe untuk diakses dari luar main thread,
        jadi bagian tulis-menulis SELALU dieksekusi lewat scheduler.
        """

        async def _fetch() -> None:
            coin = await self._source.fetch_balance(player)
            if coin is None:
                return
            self._plugin.server.scheduler.run_task(
                self._plugin, lambda: self._apply(player, coin)
            )

        self._source.run_async(_fetch())

    def sync_all_online(self) -> None:
        for player in self._plugin.server.online_players:
            self.sync_player(player)

    # ---- Internal ----------------------------------------------------------
    def _apply(self, player: Player, coin: int) -> None:
        money = self._target.get_balance(player)
        if money is None:
            return

        if coin == money:
            return  # sudah sinkron, tidak perlu update -> hindari spam API

        if self._target.set_balance(player, coin) and self._config.debug:
            self._plugin.logger.info(
                f"[EconomyBridge] Sync {player.name}: {money} -> {coin}"
            )
