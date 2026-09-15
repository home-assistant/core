"""Constants for the Control4 integration."""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Self

from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.websocket import C4Websocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE

DOMAIN = "control4"


class ReentrantAsyncLock:
    """An asyncio.Lock the same task can safely re-acquire without deadlocking."""

    def __init__(self) -> None:
        """Initialize with no owner and an unlocked underlying lock."""
        self._lock = asyncio.Lock()
        self._owner: asyncio.Task[Any] | None = None
        self._count = 0

    def locked(self) -> bool:
        """Return whether a different task currently holds this lock."""
        return self._lock.locked() and self._owner is not asyncio.current_task()

    async def __aenter__(self) -> Self:
        """Acquire the lock, or re-enter it if this task already holds it."""
        current = asyncio.current_task()
        if self._owner is current:
            self._count += 1
            return self
        await self._lock.acquire()
        self._owner = current
        self._count = 1
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Release the lock once the outermost `async with` exits."""
        self._count -= 1
        if self._count == 0:
            self._owner = None
            self._lock.release()


@dataclass
class Control4RuntimeData:
    """Runtime data for a Control4 config entry.

    account/director/websocket are always present once the entry has finished
    setup; the rest are set once during async_setup_entry. cancel_token_refresh_callback
    starts unset because it's only assigned after the first refresh is scheduled.
    """

    account: C4Account
    director: C4Director
    websocket: C4Websocket
    controller_unique_id: str = ""
    director_sw_version: str = ""
    director_model: str = ""
    director_all_items: list[dict[str, Any]] = field(default_factory=list)
    ui_configuration: dict[str, Any] | None = None
    cancel_token_refresh_callback: CALLBACK_TYPE | None = None
    cancel_periodic_resync_callback: CALLBACK_TYPE | None = None
    token_refresh_lock: ReentrantAsyncLock = field(default_factory=ReentrantAsyncLock)
    resync_lock: ReentrantAsyncLock = field(default_factory=ReentrantAsyncLock)


type Control4ConfigEntry = ConfigEntry[Control4RuntimeData]

CONF_CONTROLLER_UNIQUE_ID = "controller_unique_id"

CONTROL4_ENTITY_TYPE = 7

RETRY_BACKOFF_MAX_SEC = 30
SCHEDULE_REFRESH_ADVANCE_SEC = 300

DEFAULT_SCAN_INTERVAL = 5
WEBSOCKET_RESYNC_INTERVAL_SEC = 60
