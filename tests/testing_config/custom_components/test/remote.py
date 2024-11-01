"""Provide a mock remote platform.

Call init before using it in your tests to ensure clean test data.
"""

from homeassistant.components.remote import RemoteEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from tests.common import MockToggleEntity

ENTITIES = []


def init(empty=False):
    """Initialize the platform with entities."""
    # pylint: disable-next=global-statement
    global ENTITIES  # noqa: PLW0603

    ENTITIES = (
        []
        if empty
        else [
            MockRemote("TV", STATE_ON),
            MockRemote("DVD", STATE_OFF),
            MockRemote(None, STATE_OFF),
        ]
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities_callback: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)


class MockRemote(MockToggleEntity, RemoteEntity):
    """Mock remote class."""

    supported_features = 0
