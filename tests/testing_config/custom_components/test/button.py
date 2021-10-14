"""
Provide a mock button platform.

Call init before using it in your tests to ensure clean test data.
"""
from datetime import datetime

from homeassistant.components.button import ButtonEntity
from homeassistant.util import dt as dt_util

from tests.common import MockEntity

UNIQUE_BUTTON_1 = "unique_button_1"

ENTITIES = []


class MockButtonEntity(MockEntity, ButtonEntity):
    """Mock Button class."""

    def press(self) -> None:
        """Press the button."""
        self._attr_last_pressed = datetime(2021, 1, 1, 23, 59, 59, tzinfo=dt_util.UTC)


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockButtonEntity(
                name="button 1",
                unique_id="unique_button_1",
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
