"""EconomyBridgePlugin - main plugin entry point.

This class is intentionally kept as thin as possible ("thin controller"):
it only wires up other components (ConfigManager, providers, BridgeManager,
SyncTask) and bridges Endstone's lifecycle (on_load/on_enable/on_disable)
plus the command. The actual business logic lives in BridgeManager &
SyncTask.
"""
from __future__ import annotations

from endstone.command import Command, CommandSender
from endstone.plugin import Plugin

from .bridge_manager import BridgeManager
from .config_manager import ConfigManager
from .providers.jweconomy_provider import JWEconomyProvider
from .providers.umoney_provider import UMoneyProvider
from .sync_state_store import SyncStateStore


class EconomyBridgePlugin(Plugin):
    api_version = "0.10"

    name = "economy_bridge"
    version = "1.0.0"
    description = "Two-way balance sync between JWEconomy (Coin) and uMoney (Money)."
    authors = ["Senior Java/Endstone Developer"]
    prefix = "EconomyBridge"

    # Dua-duanya hanya soft_depend, bukan depend: kita ingin menangani
    # sendiri kasus "plugin tidak ditemukan" dengan pesan warning kustom
    # dan men-disable diri sendiri secara terkontrol (lihat on_enable),
    # bukan dibiarkan gagal load secara diam-diam oleh loader.
    soft_depend = ["jweconomy", "umoney"]

    commands = {
        "ecobridge": {
            "description": "Perintah administrasi EconomyBridge.",
            "usages": ["/ecobridge (sync|reload|status)<action: EcoBridgeAction>"],
            "permissions": ["economy_bridge.command.ecobridge"],
        }
    }

    permissions = {
        "economy_bridge.command.ecobridge": {
            "description": "Mengizinkan penggunaan perintah /ecobridge.",
            "default": "op",
        }
    }

    def __init__(self) -> None:
        super().__init__()
        self._config: ConfigManager | None = None
        self._jweconomy: JWEconomyProvider | None = None
        self._umoney: UMoneyProvider | None = None
        self._bridge: BridgeManager | None = None
        self._sync_task = None

    # ---- Lifecycle Endstone --------------------------------------------
    def on_load(self) -> None:
        self.logger.info("[EconomyBridge] Loading...")

    def on_enable(self) -> None:
        self._config = ConfigManager(self)
        self._jweconomy = JWEconomyProvider(self, currency=self._config.currency)
        self._umoney = UMoneyProvider(self)

        # --- Validasi dependensi: WAJIB kedua plugin tersedia -----------
        missing = []
        if not self._jweconomy.is_available():
            missing.append("JWEconomy (jweconomy)")
        if not self._umoney.is_available():
            missing.append("uMoney (umoney)")

        if missing:
            self.logger.warning(
                "[EconomyBridge] Plugin dependensi tidak ditemukan: "
                f"{', '.join(missing)}. EconomyBridge akan dinonaktifkan."
            )
            self.server.plugin_manager.disable_plugin(self)
            return

        self._bridge = BridgeManager(
            self, self._config, self._jweconomy, self._umoney, SyncStateStore(self)
        )
        self.register_events(self._bridge)

        # Import lazily-created SyncTask di sini agar tidak dobel wiring
        from .sync_task import SyncTask

        self._sync_task = SyncTask(self, self._config, self._bridge)
        self._sync_task.start()

        self.logger.info(
            "[EconomyBridge] Enabled. JWEconomy <-> uMoney akan disinkronkan dua arah "
            "(saldo tertinggi menang saat konflik)."
        )

    def on_disable(self) -> None:
        if self._sync_task is not None:
            self._sync_task.stop()
        self.logger.info("[EconomyBridge] Disabled.")

    # ---- Command ------------------------------------------------------
    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        if command.name != "ecobridge":
            return False

        if self._bridge is None or self._config is None:
            sender.send_message("EconomyBridge belum aktif.")
            return True

        sub = args[0].lower() if args else "status"

        if sub == "sync":
            self._bridge.sync_all_online()
            sender.send_message("EconomyBridge: sinkronisasi manual dijalankan untuk semua player online.")
        elif sub == "reload":
            self._config.reload()
            if self._sync_task is not None:
                self._sync_task.restart()
            sender.send_message("EconomyBridge: config.yml dimuat ulang.")
        elif sub == "status":
            interval = self._config.sync_interval_seconds
            status = "nonaktif" if interval <= 0 else f"setiap {interval} detik"
            sender.send_message(
                "EconomyBridge status:\n"
                f"- debug: {self._config.debug}\n"
                f"- sync-on-join: {self._config.sync_on_join}\n"
                f"- scheduler: {status}"
            )
        else:
            sender.send_message("Penggunaan: /ecobridge <sync|reload|status>")

        return True
