# EconomyBridge

Plugin Endstone (Python) untuk sinkronisasi **satu arah**:

```
JWEconomy (Coin)  --->  uMoney (Money)
```

JWEconomy adalah **Source of Truth**. uMoney tidak pernah mengubah saldo JWEconomy.

## Kenapa Python, bukan Java?

Endstone **tidak mendukung plugin Java** — hanya Python dan C++. Proyek ini
dibangun sebagai plugin Python resmi Endstone, dengan arsitektur yang tetap
mengikuti prinsip SOLID (abstraksi provider, pemisahan tanggung jawab per
class) sebagaimana diminta di requirement awal.

## Struktur

```
economy-bridge/
├── pyproject.toml
├── README.md
└── src/endstone_economy_bridge/
    ├── __init__.py
    ├── plugin.py                     # EconomyBridgePlugin (main class)
    ├── config_manager.py             # ConfigManager
    ├── bridge_manager.py             # BridgeManager (logika sinkronisasi)
    ├── sync_task.py                  # SyncTask (scheduler berkala)
    ├── economy_provider.py           # Abstraksi provider
    ├── resources/config.yml          # Default config yang dibundel
    └── providers/
        ├── jweconomy_provider.py     # Adapter JWEconomy (source, async)
        └── umoney_provider.py        # Adapter uMoney (target, sync)
```

## Penjelasan Singkat Tiap Class

| Class | Tanggung Jawab |
|---|---|
| `EconomyBridgePlugin` | Entry point plugin: wiring komponen, lifecycle (`on_load`/`on_enable`/`on_disable`), dan command `/ecobridge`. |
| `ConfigManager` | Membaca/menulis `config.yml` (bukan `config.toml` bawaan Endstone), menyediakan default yang aman. |
| `EconomyProvider` (`SourceEconomyProvider` / `TargetEconomyProvider`) | Kontrak abstrak agar provider ekonomi baru mudah ditambahkan tanpa mengubah `BridgeManager`. |
| `JWEconomyProvider` | Adapter ke JWEconomy. API-nya **async**, dipanggil lewat `run_async()` milik JWEconomy sendiri. Hanya membaca saldo (read-only). |
| `UMoneyProvider` | Adapter ke uMoney. API-nya sinkron biasa, dibaca & ditulis (`api_get_player_money` / `api_reset_player_money`). |
| `BridgeManager` | Logika inti: dengar `PlayerJoinEvent`, bandingkan saldo, tulis ke uMoney **hanya jika berbeda**, log jika `debug: true`. |
| `SyncTask` | Menjadwalkan `BridgeManager.sync_all_online()` secara berkala lewat `server.scheduler`, interval dari `config.yml`. |

## Kenapa Tidak Ada Event "Coin Berubah" secara Real-time?

Berdasarkan source code JWEconomy (`junggamyeon/JWEconomy`) saat ini, plugin
tersebut **tidak mengekspos event** saat saldo berubah (baik lewat command,
shop, reward quest, maupun reward battle). Karena itu mekanisme yang
realistis dan robust adalah:

1. **Sync saat join** (`sync-on-join: true`) — menutup celah saat player baru masuk.
2. **Scheduler berkala** (`sync-interval`, detik) — menutup semua kasus lain
   (command add/remove coin, shop, reward, dll) dalam rentang waktu maksimal
   sebesar nilai interval tersebut.

Jika di masa depan JWEconomy menambahkan event perubahan saldo, cukup
tambahkan `@event_handler` baru di `BridgeManager` yang memanggil
`sync_player()` — tidak perlu mengubah komponen lain.

## Command

- `/ecobridge sync` — paksa sinkronisasi semua player online sekarang.
- `/ecobridge reload` — muat ulang `config.yml` & restart scheduler.
- `/ecobridge status` — tampilkan status konfigurasi saat ini.

Permission: `economy_bridge.command.ecobridge` (default: **op**).

## Instalasi

```bash
pip install build
cd economy-bridge
python -m build --wheel
```

Salin file `.whl` hasil build (di folder `dist/`) ke folder `plugins/` server
Endstone kamu, lalu jalankan server. `config.yml` akan otomatis dibuat di
`plugins/economy_bridge/config.yml` saat plugin pertama kali di-enable.

## Bagian yang WAJIB Diverifikasi Ulang di Server Kamu

Karena API pihak ketiga bisa berubah antar versi, cek kembali (ditandai
`# TODO` di kode):

1. `JWEconomyProvider.PLUGIN_NAME` — nama plugin JWEconomy di `plugin_manager`.
2. `JWEconomyProvider`: cara mendapatkan API (`get_api()`) dan signature
   `get_balance(uuid, currency)`.
3. `UMoneyProvider.PLUGIN_NAME` — nama plugin uMoney di `plugin_manager`.
4. `UMoneyProvider`: nama method `api_get_player_money` /
   `api_reset_player_money`.
