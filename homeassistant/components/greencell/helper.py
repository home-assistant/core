from typing import Callable
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
        if new_access_level == 'DISABLED':
            self._access_level = AccessLevel.DISABLED
        elif new_access_level == 'READ':
            self._access_level = AccessLevel.READ_ONLY
        elif new_access_level == 'EXECUTE':
            self._access_level = AccessLevel.EXECUTE
        elif new_access_level == 'OFFLINE':
            self._access_level = AccessLevel.OFFLINE
        else:
            _LOGGER.error(f'Invalid access level: {new_access_level}')
            return

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
        return self._access_level == AccessLevel.DISABLED or self._access_level == AccessLevel.OFFLINE
