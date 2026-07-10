"""Adapter untuk uMoney (target sinkronisasi / "Money").

Berdasarkan source code resmi uMoney (U-Blocks/UMoney):
    um = self.server.plugin_manager.get_plugin("umoney")
    money = um.api_get_player_money(player_name)          # SYNC, key by NAME
    um.api_reset_player_money(player_name, amount)         # set nilai eksak
    um.api_change_player_money(player_name, delta)         # delta (tidak dipakai di sini)

EconomyBridge selalu memakai ``api_reset_player_money`` (set eksak) karena
kita ingin uMoney == JWEconomy secara pasti, bukan menambah/mengurangi
selisih (yang rawan drift bila ada balapan/race condition).

Bagian yang perlu disesuaikan jika versi uMoney di server kamu berbeda:
    - ``PLUGIN_NAME``: nama plugin sebagaimana terdaftar di plugin_manager.
    - Nama method ``api_get_player_money`` / ``api_reset_player_money``.
"""
from __future__ import annotations

from typing import Optional

from endstone import Player
from endstone.plugin import Plugin

from ..economy_provider import SyncEconomyProvider


class UMoneyProvider(SyncEconomyProvider):
    # TODO: sesuaikan bila nama plugin uMoney di server kamu berbeda
    PLUGIN_NAME = "umoney"

    def __init__(self, host_plugin: Plugin) -> None:
        self._host = host_plugin
        self._umoney_plugin = None

    @property
    def display_name(self) -> str:
        return "uMoney"

    def is_available(self) -> bool:
        self._umoney_plugin = self._host.server.plugin_manager.get_plugin(self.PLUGIN_NAME)
        return self._umoney_plugin is not None

    def get_balance(self, player: Player) -> Optional[int]:
        if self._umoney_plugin is None and not self.is_available():
            return None
        try:
            # TODO: sesuaikan bila nama method berubah di versi lain
            return int(self._umoney_plugin.api_get_player_money(player.name))
        except Exception as exc:
            self._host.logger.error(
                f"[EconomyBridge] Gagal membaca saldo uMoney untuk "
                f"{player.name}: {exc}"
            )
            return None

    def set_balance(self, player: Player, amount: int) -> bool:
        if self._umoney_plugin is None and not self.is_available():
            return False
        try:
            # TODO: sesuaikan bila nama method berubah di versi lain
            self._umoney_plugin.api_reset_player_money(player.name, int(amount))
            return True
        except Exception as exc:
            self._host.logger.error(
                f"[EconomyBridge] Gagal mengubah saldo uMoney untuk "
                f"{player.name}: {exc}"
            )
            return False
