"""Context-local routing primitive for sandboxed integrations.

A sandbox runtime (``sandbox``) runs integrations in an isolated
subprocess. Core HA primitives such as :class:`homeassistant.helpers.storage.Store`
must, inside that subprocess, route their IO to main instead of touching
the sandbox's local disk. Rather than monkey-patching the ``Store`` class
at module scope (the v1 footgun), the runtime sets a :class:`~contextvars.ContextVar`
that those primitives read at call time.

The shape mirrors the existing module-level ContextVars in this package —
``helpers/http.py::current_request`` and
``helpers/chat_session.py::current_session``: a module-level
``ContextVar[T | None]`` with ``default=None``.

Hard rule (see the plan's Risk #3): **never set ``current_sandbox`` from
main-side code.** It is set exactly once, early in the sandbox runtime's
``run()``, and inherited by every coroutine the runtime spawns (asyncio
copies the context at ``create_task`` time). Setting it on main's event
loop would silently reroute main's own ``Store`` IO to a bridge.
"""

from contextvars import ContextVar
from typing import Any, Protocol


class SandboxBridge(Protocol):
    """Per-sandbox routing surface, populated by the sandbox runtime.

    Today this carries only the three ``Store`` IO methods. The protocol
    is forward-compatible with cross-sandbox sub-namespaces (IR / RF /
    BLE): a future plan adds e.g. ``infrared: InfraredBridge`` without
    touching the existing methods or their callers.

    ``async_store_load`` returns the *wrapped* storage envelope
    (``{"version", "minor_version", "key", "data"}``) or ``None`` — the
    migration loop in ``Store`` runs against it unchanged, regardless of
    whether the dict came from disk or from a bridge.
    """

    async def async_store_load(self, key: str) -> Any:
        """Return the wrapped storage envelope for ``key`` (or ``None``)."""

    async def async_store_save(self, key: str, data: Any) -> None:
        """Persist the wrapped storage envelope ``data`` under ``key``."""

    async def async_store_remove(self, key: str) -> None:
        """Remove the stored data for ``key``."""


current_sandbox: ContextVar[SandboxBridge | None] = ContextVar(
    "current_sandbox", default=None
)
