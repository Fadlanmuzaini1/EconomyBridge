"""EconomyBridgePlugin - titik masuk utama plugin.

Tanggung jawab class ini SENGAJA dibuat setipis mungkin ("thin
controller"): hanya menyusun (wiring) komponen-komponen lain
(ConfigManager, provider, BridgeManager, SyncTask) dan menjembatani
lifecycle Endstone (on_load/on_enable/on_disable) serta command.
Logika bisnis sesungguhnya hidup di BridgeManager & SyncTask.
"""
from __future__ import annotations

from endstone.command import Command, CommandSender
from endstone.plugin import Plugin

from .bridge_manager import BridgeManager
from .config_manager import ConfigManager
from .providers.jweconomy_provider import JWEconomyProvider
from .providers.umoney_provider import UMoneyProvider


class EconomyBridgePlugin(Plugin):
    api_version = "0.10"

    name = "economy_bridge"
    version = "1.0.0"
    description = "Sinkronisasi satu arah JWEconomy (Coin) -> uMoney (Money)."
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
        self._source: JWEconomyProvider | None = None
        self._target: UMoneyProvider | None = None
        self._bridge: BridgeManager | None = None
        self._sync_task = None

    # ---- Lifecycle Endstone --------------------------------------------
    def on_load(self) -> None:
        self.logger.info("[EconomyBridge] Loading...")

    def on_enable(self) -> None:
        self._config = ConfigManager(self)
        self._source = JWEconomyProvider(self, currency=self._config.currency)
        self._target = UMoneyProvider(self)

        # --- Validasi dependensi: WAJIB kedua plugin tersedia -----------
        missing = []
        if not self._source.is_available():
            missing.append("JWEconomy (jweconomy)")
        if not self._target.is_available():
            missing.append("uMoney (umoney)")

        if missing:
            self.logger.warning(
                "[EconomyBridge] Plugin dependensi tidak ditemukan: "
                f"{', '.join(missing)}. EconomyBridge akan dinonaktifkan."
            )
            self.server.plugin_manager.disable_plugin(self)
            return

        self._bridge = BridgeManager(self, self._config, self._source, self._target)
        self.register_events(self._bridge)

        # Import lazily-created SyncTask di sini agar tidak dobel wiring
        from .sync_task import SyncTask

        self._sync_task = SyncTask(self, self._config, self._bridge)
        self._sync_task.start()

        self.logger.info("[EconomyBridge] Enabled. JWEconomy -> uMoney siap disinkronkan.")

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
