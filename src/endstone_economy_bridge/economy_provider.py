"""Provider abstraction for EconomyBridge.

Two-way sync means BOTH sides now need read AND write. The only real
difference between them is *how* they're called:

- JWEconomy: every balance method is ``async`` (must be awaited inside an
  ``async def``, run through the plugin's own event-loop via
  ``plugin.run_async(coro)``).
- uMoney: every balance method is a plain synchronous call.

That calling-convention difference is important enough to keep as two
separate base classes (rather than hiding it behind one generic
interface), so it stays obvious at every call site whether you're crossing
into async territory or not. Both still share the common contract via
``EconomyProvider``.

Adding another economy plugin later is just a matter of extending whichever
base class matches its calling convention, without touching BridgeManager.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from endstone import Player


class EconomyProvider(ABC):
    """Shared base contract for all economy providers."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Name of the economy plugin, used for logging & error messages."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if the underlying plugin is detected and its API is ready."""


class AsyncEconomyProvider(EconomyProvider):
    """Provider whose balance API is asynchronous (e.g. JWEconomy)."""

    @abstractmethod
    async def get_balance(self, player: Player) -> Optional[int]:
        """Fetch the player's current balance. Returns None on failure."""

    @abstractmethod
    async def set_balance(self, player: Player, amount: int) -> bool:
        """Set the player's balance to an exact value. Returns True on success."""

    @abstractmethod
    def run_async(self, coro) -> None:
        """Run a coroutine through this plugin's own event-loop."""


class SyncEconomyProvider(EconomyProvider):
    """Provider whose balance API is plain synchronous (e.g. uMoney)."""

    @abstractmethod
    def get_balance(self, player: Player) -> Optional[int]:
        """Fetch the player's current balance. Returns None on failure."""

    @abstractmethod
    def set_balance(self, player: Player, amount: int) -> bool:
        """Set the player's balance to an exact value. Returns True on success."""
