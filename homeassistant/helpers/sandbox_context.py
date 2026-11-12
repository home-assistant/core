"""Context-local routing primitive for sandboxed integrations."""

from contextvars import ContextVar
from typing import Any, Protocol


class SandboxBridge(Protocol):
    """Per-sandbox routing surface, populated by the sandbox runtime."""

    async def async_store_load(self, key: str) -> Any:
        """Return the wrapped storage envelope for ``key`` (or ``None``)."""

    async def async_store_save(self, key: str, data: Any) -> None:
        """Persist the wrapped storage envelope ``data`` under ``key``."""

    async def async_store_remove(self, key: str) -> None:
        """Remove the stored data for ``key``."""


current_sandbox: ContextVar[SandboxBridge | None] = ContextVar(
    "current_sandbox", default=None
)
