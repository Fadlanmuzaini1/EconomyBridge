"""Adapter for JWEconomy (one side of the two-way sync).

Based on the official JWEconomy README (junggamyeon/JWEconomy):
    jwe = self.server.plugin_manager.get_plugin("jweconomy")
    api = jwe.get_api()
    balance = await api.get_balance(uuid_str, currency)   # every balance method is async
    new_balance = await api.set_balance(uuid_str, amount, currency)
    jwe.run_async(coro)                                    # how to run a coroutine

Things to double-check if your JWEconomy version differs:
    - ``PLUGIN_NAME``: the name it's registered under in plugin_manager.
    - The ``api.get_balance(uuid, currency)`` / ``api.set_balance(uuid, amount, currency)``
      signatures, in case they change in a future release.
"""
from __future__ import annotations

from typing import Optional

from endstone import Player
from endstone.plugin import Plugin

from ..economy_provider import AsyncEconomyProvider


class JWEconomyProvider(AsyncEconomyProvider):
    # TODO: adjust if JWEconomy is registered under a different name on your server
    PLUGIN_NAME = "jweconomy"

    def __init__(self, host_plugin: Plugin, currency: Optional[str] = None) -> None:
        self._host = host_plugin
        self._currency = currency  # None => use JWEconomy's default currency
        self._jwe_plugin = None
        self._api = None

    @property
    def display_name(self) -> str:
        return "JWEconomy"

    def is_available(self) -> bool:
        self._jwe_plugin = self._host.server.plugin_manager.get_plugin(self.PLUGIN_NAME)
        if self._jwe_plugin is None:
            return False
        try:
            # TODO: adjust if the way to obtain the API changes in a future release
            self._api = self._jwe_plugin.get_api()
        except Exception as exc:  # defensive: never let this crash the server
            self._host.logger.error(
                f"[EconomyBridge] Failed to obtain JWEconomy API: {exc}"
            )
            return False
        return self._api is not None

    async def get_balance(self, player: Player) -> Optional[int]:
        """Fetch the player's Coin balance. Must be called inside a coroutine
        run via run_async(), NOT directly on the main thread."""
        if self._api is None and not self.is_available():
            return None
        try:
            uuid = str(player.unique_id)
            # TODO: adjust if the get_balance() signature changes
            balance = await self._api.get_balance(uuid, self._currency)
            return round(balance)
        except Exception as exc:
            self._host.logger.error(
                f"[EconomyBridge] Failed to read JWEconomy balance for "
                f"{player.name}: {exc}"
            )
            return None

    async def set_balance(self, player: Player, amount: int) -> bool:
        """Set the player's Coin balance to an exact value."""
        if self._api is None and not self.is_available():
            return False
        try:
            uuid = str(player.unique_id)
            # TODO: adjust if the set_balance() signature changes
            await self._api.set_balance(uuid, amount, self._currency)
            return True
        except Exception as exc:
            self._host.logger.error(
                f"[EconomyBridge] Failed to write JWEconomy balance for "
                f"{player.name}: {exc}"
            )
            return False

    def run_async(self, coro) -> None:
        """Run a coroutine through JWEconomy's own event-loop.

        JWEconomy's API must NEVER be awaited directly on the main Endstone
        thread (it isn't async-aware), so every call goes through
        JWEconomy's own run_async().
        """
        if self._jwe_plugin is None and not self.is_available():
            self._host.logger.error(
                "[EconomyBridge] JWEconomy is unavailable, sync cancelled."
            )
            return
        try:
            self._jwe_plugin.run_async(coro)
        except Exception as exc:
            self._host.logger.error(
                f"[EconomyBridge] Failed to schedule an async JWEconomy task: {exc}"
            )
