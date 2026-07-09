"""Adapter untuk JWEconomy (Source of Truth / "JWEssentials" Coin).

Berdasarkan README resmi JWEconomy (junggamyeon/JWEconomy):
    jwe = self.server.plugin_manager.get_plugin("jweconomy")
    api = jwe.get_api()
    balance = await api.get_balance(uuid_str, currency)   # SEMUA method saldo async
    jwe.run_async(coro)                                   # cara menjalankan coroutine

Bagian yang perlu disesuaikan jika versi JWEconomy di server kamu berbeda:
    - ``PLUGIN_NAME``: nama plugin sebagaimana terdaftar di plugin_manager.
    - Signature ``api.get_balance(uuid, currency)`` bila method/parameter
      berubah pada rilis mendatang.
"""
from __future__ import annotations

from typing import Optional

from endstone import Player
from endstone.plugin import Plugin

from ..economy_provider import SourceEconomyProvider


class JWEconomyProvider(SourceEconomyProvider):
    # TODO: sesuaikan bila nama plugin JWEconomy di server kamu berbeda
    PLUGIN_NAME = "jweconomy"

    def __init__(self, host_plugin: Plugin, currency: Optional[str] = None) -> None:
        self._host = host_plugin
        self._currency = currency  # None => pakai currency default JWEconomy
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
            # TODO: sesuaikan bila cara mengambil API berubah di versi lain
            self._api = self._jwe_plugin.get_api()
        except Exception as exc:  # defensif: jangan sampai server crash
            self._host.logger.error(
                f"[EconomyBridge] Gagal mengambil API JWEconomy: {exc}"
            )
            return False
        return self._api is not None

    async def fetch_balance(self, player: Player) -> Optional[int]:
        """Ambil saldo Coin milik player. Dipanggil di dalam coroutine yang
        dijalankan lewat run_async(), BUKAN langsung di main thread."""
        if self._api is None and not self.is_available():
            return None
        try:
            uuid = str(player.unique_id)
            # TODO: sesuaikan bila signature get_balance() berubah
            balance = await self._api.get_balance(uuid, self._currency)
            return round(balance)
        except Exception as exc:
            self._host.logger.error(
                f"[EconomyBridge] Gagal mengambil saldo JWEconomy untuk "
                f"{player.name}: {exc}"
            )
            return None

    def run_async(self, coro) -> None:
        """Jalankan coroutine lewat event-loop internal JWEconomy.

        JWEconomy TIDAK boleh dipanggil langsung dengan await di main
        thread Endstone (bukan async), sehingga wajib lewat run_async
        milik plugin JWEconomy itu sendiri.
        """
        if self._jwe_plugin is None and not self.is_available():
            self._host.logger.error(
                "[EconomyBridge] JWEconomy tidak tersedia, sinkronisasi dibatalkan."
            )
            return
        try:
            self._jwe_plugin.run_async(coro)
        except Exception as exc:
            self._host.logger.error(
                f"[EconomyBridge] Gagal menjalankan tugas async JWEconomy: {exc}"
            )
