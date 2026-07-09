"""Mengelola pembacaan & penyimpanan config.yml plugin.

Endstone secara bawaan menyediakan config berbasis config.toml lewat
Plugin.config / Plugin.reload_config(). Karena requirement proyek ini
eksplisit meminta config.yml, ConfigManager mengimplementasikan
penyimpanan/parsing YAML sendiri memakai PyYAML, independen dari
mekanisme config.toml bawaan Endstone.
"""
from __future__ import annotations

import os
import shutil
from importlib import resources
from typing import Any, Optional

import yaml
from endstone.plugin import Plugin

# Nilai default dipakai sebagai fallback bila config.yml pengguna korup
# atau ada key yang hilang (mis. setelah update plugin menambah key baru).
_DEFAULTS: dict[str, Any] = {
    "debug": False,
    "sync-on-join": True,
    "sync-interval": 60,
    "currency": None,
}


class ConfigManager:
    def __init__(self, plugin: Plugin) -> None:
        self._plugin = plugin
        self._path = os.path.join(plugin.data_folder, "config.yml")
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self.load()

    def load(self) -> None:
        os.makedirs(self._plugin.data_folder, exist_ok=True)

        if not os.path.isfile(self._path):
            self._copy_bundled_default()

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
        except Exception as exc:
            self._plugin.logger.error(
                f"[EconomyBridge] Gagal membaca config.yml, memakai nilai default: {exc}"
            )
            loaded = {}

        settings = loaded.get("settings") or {}
        merged = dict(_DEFAULTS)
        merged.update(settings)
        self._data = merged

    def reload(self) -> None:
        self.load()

    def _copy_bundled_default(self) -> None:
        """Salin config.yml default yang dibundel di dalam package."""
        try:
            bundled = resources.files("endstone_economy_bridge.resources").joinpath("config.yml")
            with resources.as_file(bundled) as bundled_path:
                shutil.copyfile(bundled_path, self._path)
        except Exception as exc:
            # Fallback terakhir: tulis default minimal tanpa komentar
            self._plugin.logger.warning(
                f"[EconomyBridge] Gagal menyalin config.yml bawaan ({exc}), "
                "menulis default minimal."
            )
            with open(self._path, "w", encoding="utf-8") as f:
                yaml.safe_dump({"settings": _DEFAULTS}, f, sort_keys=False)

    # ---- Accessor ----------------------------------------------------
    @property
    def debug(self) -> bool:
        return bool(self._data.get("debug", False))

    @property
    def sync_on_join(self) -> bool:
        return bool(self._data.get("sync-on-join", True))

    @property
    def sync_interval_seconds(self) -> int:
        try:
            value = int(self._data.get("sync-interval", 60))
        except (TypeError, ValueError):
            value = 60
        return max(0, value)

    @property
    def currency(self) -> Optional[str]:
        return self._data.get("currency")
