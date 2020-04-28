"""
Provide a mock lock platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.lock import SUPPORT_OPEN, LockEntity

from tests.common import MockEntity

ENTITIES = {}


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        {}
        if empty
        else {
            "support_open": MockLock(
                name=f"Support open Lock",
                is_locked=True,
                supported_features=SUPPORT_OPEN,
                unique_id="unique_support_open",
            ),
            "no_support_open": MockLock(
                name=f"No support open Lock",
                is_locked=True,
                supported_features=0,
                unique_id="unique_no_support_open",
            ),
        }
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(list(ENTITIES.values()))


class MockLock(MockEntity, LockEntity):
    """Mock Lock class."""

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        return self._handle("is_locked")

    @property
    def supported_features(self):
        """Return the class of this sensor."""
        return self._handle("supported_features")
