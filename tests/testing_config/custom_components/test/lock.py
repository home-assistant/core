"""Provide a mock lock platform.

Call init before using it in your tests to ensure clean test data.
"""

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from tests.common import MockEntity

ENTITIES = {}


def init(empty=False):
    """Initialize the platform with entities."""
    # pylint: disable-next=global-statement
    global ENTITIES  # noqa: PLW0603

    ENTITIES = (
        {}
        if empty
        else {
            "support_open": MockLock(
                name="Support open Lock",
                is_locked=True,
                supported_features=LockEntityFeature.OPEN,
                unique_id="unique_support_open",
            ),
            "no_support_open": MockLock(
                name="No support open Lock",
                is_locked=True,
                supported_features=0,
                unique_id="unique_no_support_open",
            ),
        }
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities_callback: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Return mock entities."""
    async_add_entities_callback(list(ENTITIES.values()))


class MockLock(MockEntity, LockEntity):
    """Mock Lock class."""

    @property
    def code_format(self) -> str | None:
        """Return code format."""
        return self._handle("code_format")

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        return self._handle("is_locked")

    @property
    def supported_features(self):
        """Return the class of this sensor."""
        return self._handle("supported_features")
