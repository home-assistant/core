"""helper.py

Helper class for managing Home Assistant access levels for Greencell EVSE devices.

Classes:
- GreencellAccess: tracks the current access level (DISABLED, READ_ONLY, EXECUTE, OFFLINE),
  notifies registered listeners on changes, and provides utility methods:
    * update(new_access_level: str) – parse and set a new access level from its string name.
    * register_listener(listener: Callable) – add callbacks to invoke when access changes.
    * can_execute() -> bool – returns True if the level allows executing commands.
    * is_disabled() -> bool – returns True if access is DISABLED or OFFLINE.
"""

from collections.abc import Callable
import logging

from .const import GreencellHaAccessLevelEnum as AccessLevel

_LOGGER = logging.getLogger(__name__)


class GreencellAccess:
    """Class to manage access levels for Greencell devices."""

    def __init__(self, access_level: AccessLevel):
        self._access_level = access_level
        self._listeners = []

    def update(self, new_access_level: str) -> None:
        """Update the access level and notify listeners."""
        self._access_level = AccessLevel.__members__.get(
            new_access_level, AccessLevel.DISABLED
        )
        self._notify_listeners()

    def register_listener(self, listener: Callable[[], None]) -> None:
        """Register a listener to be notified when the access level changes."""
        self._listeners.append(listener)

    def _notify_listeners(self) -> None:
        """Notify all registered listeners of the access level change."""
        for listener in self._listeners:
            listener()

    def can_execute(self) -> bool:
        """Check if the current access level allows execution of commands."""
        return self._access_level == AccessLevel.EXECUTE

    def is_disabled(self) -> bool:
        """Check if the current access level is disabled."""
        return (
            self._access_level == AccessLevel.DISABLED
            or self._access_level == AccessLevel.OFFLINE
        )
