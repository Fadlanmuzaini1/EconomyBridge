"""SyncTask - sinkronisasi berkala (backup) via Endstone Scheduler.

Dipakai untuk menangkap perubahan Coin yang tidak lewat event yang bisa
kita dengar (reward quest, reward battle, shop, command pihak ketiga,
dsb) — karena JWEconomy tidak mengekspos event perubahan saldo. Interval
diatur lewat config.yml (`sync-interval`, satuan detik). Isi 0 untuk
mematikan scheduler ini sepenuhnya.
"""
from __future__ import annotations

from endstone.plugin import Plugin

from .bridge_manager import BridgeManager
from .config_manager import ConfigManager

_TICKS_PER_SECOND = 20


class SyncTask:
    def __init__(self, plugin: Plugin, config: ConfigManager, bridge: BridgeManager) -> None:
        self._plugin = plugin
        self._config = config
        self._bridge = bridge
        self._task = None

    def start(self) -> None:
        interval = self._config.sync_interval_seconds
        if interval <= 0:
            self._plugin.logger.info(
                "[EconomyBridge] sync-interval = 0, scheduler berkala dimatikan."
            )
            return

        period_ticks = interval * _TICKS_PER_SECOND
        self._task = self._plugin.server.scheduler.run_task(
            self._plugin,
            self._run,
            delay=period_ticks,
            period=period_ticks,
        )
        if self._config.debug:
            self._plugin.logger.info(
                f"[EconomyBridge] Scheduler berkala aktif setiap {interval} detik."
            )

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def _run(self) -> None:
        self._bridge.sync_all_online()
