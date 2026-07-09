"""Abstraksi provider ekonomi untuk EconomyBridge.

Kenapa ada dua sub-interface (bukan satu EconomyProvider generik)?
Berdasarkan API asli kedua plugin target:

- JWEconomy: SELURUH method saldo bersifat ``async`` (harus di-``await``
  di dalam ``async def``, dijalankan lewat event-loop internal plugin
  tersebut via ``plugin.run_async(coro)``). Plugin ini juga berperan
  sebagai *Source of Truth* sehingga BridgeManager hanya pernah
  MEMBACA saldo darinya, tidak pernah menulis.
- uMoney: seluruh method saldo bersifat sinkron biasa, dan berperan
  sebagai target sinkronisasi (dibaca & ditulis).

Memaksakan keduanya ke satu interface `get_balance()/set_balance()` yang
sama akan menyembunyikan perbedaan async/sync yang justru krusial untuk
dipahami saat membaca kode. Karena itu dipisah menjadi
``SourceEconomyProvider`` dan ``TargetEconomyProvider``, keduanya tetap
berbagi kontrak dasar lewat ``EconomyProvider``.

Menambah provider ekonomi baru di masa depan cukup dengan meng-extend
salah satu dari kedua base class ini, tanpa mengubah BridgeManager.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from endstone import Player


class EconomyProvider(ABC):
    """Kontrak dasar bersama untuk semua provider ekonomi."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Nama plugin ekonomi, dipakai untuk logging & pesan error."""

    @abstractmethod
    def is_available(self) -> bool:
        """True jika plugin ekonomi terkait terdeteksi & API-nya siap dipakai."""


class SourceEconomyProvider(EconomyProvider):
    """Provider yang berperan sebagai Source of Truth (read-only, async)."""

    @abstractmethod
    async def fetch_balance(self, player: Player) -> Optional[int]:
        """Ambil saldo terbaru milik player secara asynchronous.

        Mengembalikan None jika gagal (API error, plugin belum siap, dst),
        sehingga BridgeManager tahu untuk membatalkan sinkronisasi giliran
        ini alih-alih memakai data yang salah/kadaluarsa.
        """

    @abstractmethod
    def run_async(self, coro) -> None:
        """Jalankan coroutine lewat event-loop internal plugin sumber."""


class TargetEconomyProvider(EconomyProvider):
    """Provider yang berperan sebagai target sinkronisasi (read/write, sync)."""

    @abstractmethod
    def get_balance(self, player: Player) -> Optional[int]:
        """Ambil saldo saat ini milik player. Mengembalikan None jika gagal."""

    @abstractmethod
    def set_balance(self, player: Player, amount: int) -> bool:
        """Set saldo player ke nilai tertentu. Mengembalikan True jika sukses."""
