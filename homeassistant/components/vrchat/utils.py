"""Utils for the VRChat integration."""

import asyncio
import base64
from collections.abc import Awaitable, Callable
from enum import StrEnum
import inspect
import logging
from typing import Any, Final

from propcache.api import cached_property

_LOGGER = logging.getLogger(__name__)


def process_vrchat_string(s: str | None = None):
    """Process a string value returned by the VRChat API. Treat empty string as None."""
    return None if s is None or len(s) <= 0 else s


def normalize_vrchat_enum_value(s: str | None = None):
    """Normalize a VRChat enum value for use as a Home Assistant state."""
    value = process_vrchat_string(s)
    return value.replace(" ", "_") if value is not None else None


def svg_file_uri(svg: str):
    """Turn an SVG string into a data URI."""
    return f"data:image/svg+xml;charset=utf-8;base64,{base64.b64encode(svg.encode()).decode('ascii')}"


def is_user_in_game(user_data: dict[str, Any]) -> bool | None:
    """Return whether a user is present in a VRChat world."""
    location = (
        process_vrchat_string(user_data.get("location"))
        or process_vrchat_string(user_data.get("world"))
        or process_vrchat_string(user_data.get("instance"))
    )
    if location is None:
        return None
    return location not in {
        VRChatSpecialLocationString.OFFLINE,
        f"{VRChatSpecialLocationString.OFFLINE}:{VRChatSpecialLocationString.OFFLINE}",
    }


class VRChatSpecialLocationString(StrEnum):
    """VRChat special location string."""

    TRAVELING = "traveling"
    PRIVATE = "private"
    OFFLINE = "offline"


VRCHAT_SPECIAL_LOCATION_STRINGS = set(VRChatSpecialLocationString)
VRCHAT_LOCATION_STRING_DELIMITER: Final = ":"
VRCHAT_WORLD_ID_PREFIX: Final = "wrld_"


def parse_vrchat_location_string(s: str | None = None):
    """Process a VRChat location string."""
    world_id: str | None = None
    instance_id: str | None = None
    s = process_vrchat_string(s)
    if s is not None:
        for ss in VRCHAT_SPECIAL_LOCATION_STRINGS:
            if s.startswith(ss):
                world_id = ss.value
                instance_id = ss.value
                break
        if world_id is None:
            if VRCHAT_LOCATION_STRING_DELIMITER in s:
                world_id, instance_id = s.split(VRCHAT_LOCATION_STRING_DELIMITER, 1)
            elif s.startswith(VRCHAT_WORLD_ID_PREFIX):
                world_id = s
            else:
                instance_id = s
    return world_id, instance_id


EXCEPTION_MESSAGE_ASYNC_CLEANUP: Final = "Error during async clean up."
ASYNC_CLEANUP_TIMEOUT_SECOND: Final = 10


async def _async_run_cleanup(awaitable: Awaitable[Any]) -> None:
    """Run an async cleanup without blocking other cleanup callbacks."""
    try:
        async with asyncio.timeout(ASYNC_CLEANUP_TIMEOUT_SECOND):
            await awaitable
    except TimeoutError:
        _LOGGER.warning("Timed out during async clean up")
    except Exception:
        _LOGGER.exception(EXCEPTION_MESSAGE_ASYNC_CLEANUP)


class AsyncCleanups:
    """Handle async cleanup callbacks."""

    @cached_property
    def _cleanups(self) -> list[Callable]:
        return []

    @property
    def _closed(self):
        return getattr(self, "_closed_value", False)

    @_closed.setter
    def _closed(self, new_value):
        self._closed_value = new_value

    @property
    def closed(self):
        """True if object is already closed."""
        return self._closed

    def add_to_cleanups(self, callback: Callable):
        """Add a cleanup callback to be executed on closing/exiting."""
        self._cleanups.insert(0, callback)

    def remove_from_cleanups(self, callback: Callable):
        """Remove a cleanup callback."""
        if callback in self._cleanups:
            self._cleanups.remove(callback)

    async def close(self):
        """Close."""
        if self.closed:
            return
        self._closed = True
        try:
            async with asyncio.TaskGroup() as tg:
                for c in list(self._cleanups):
                    try:
                        res = c()
                    except Exception:
                        res = None
                        _LOGGER.exception(EXCEPTION_MESSAGE_ASYNC_CLEANUP)

                    if inspect.isawaitable(res):
                        tg.create_task(_async_run_cleanup(res))
        except Exception:
            _LOGGER.exception(EXCEPTION_MESSAGE_ASYNC_CLEANUP)

    async def __aenter__(self):
        """Return self."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Close."""
        await self.close()
