"""SyncStateStore - persists the last successfully-synced balance per player.

Why this is needed:
    A naive "highest balance wins" rule, applied with no memory of the
    past, breaks spending. If a player's Coin balance is REDUCED (e.g. a
    shop purchase) while Money hasn't been touched, Money would now be the
    higher value and would get pushed back into JWEconomy on the next
    cycle -- silently reverting the purchase. The exact same problem
    happens symmetrically for uMoney deductions.

    To avoid that, EconomyBridge remembers the last balance both sides
    were confirmed to agree on. On each check:
      - If only one side differs from that baseline, THAT side is the one
        that legitimately changed (whether it went up or down), and its
        value is pushed to the other side.
      - Only when BOTH sides differ from the baseline (a genuine
        simultaneous conflict) does the "highest balance wins" tie-break
        rule apply.

Storage is a small JSON file in the plugin's data folder, keyed by player
UUID (stable across name changes). This intentionally avoids any external
dependency -- plain json/os is enough for this size of data.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from endstone import Player
from endstone.plugin import Plugin


class SyncStateStore:
    def __init__(self, plugin: Plugin) -> None:
        self._plugin = plugin
        self._path = os.path.join(plugin.data_folder, "sync_state.json")
        self._data: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
            self._data = {str(k): int(v) for k, v in raw.items()}
        except Exception as exc:
            self._plugin.logger.error(
                f"[EconomyBridge] Failed to read sync_state.json, "
                f"starting with an empty baseline: {exc}"
            )
            self._data = {}

    def _save(self) -> None:
        try:
            os.makedirs(self._plugin.data_folder, exist_ok=True)
            tmp_path = self._path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f)
            os.replace(tmp_path, self._path)
        except Exception as exc:
            self._plugin.logger.error(
                f"[EconomyBridge] Failed to persist sync_state.json: {exc}"
            )

    def get(self, player: Player) -> Optional[int]:
        """Last confirmed-synced balance for this player, or None if this
        player has never been reconciled before (e.g. first join ever)."""
        return self._data.get(str(player.unique_id))

    def set(self, player: Player, balance: int) -> None:
        self._data[str(player.unique_id)] = balance
        self._save()
