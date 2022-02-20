"""
Provide a mock button platform.

Call init before using it in your tests to ensure clean test data.
"""
import logging

from homeassistant.components.button import ButtonEntity

from tests.common import MockEntity

UNIQUE_BUTTON_1 = "unique_button_1"

ENTITIES = []

_LOGGER = logging.getLogger(__name__)


class MockButtonEntity(MockEntity, ButtonEntity):
    """Mock Button class."""

    def press(self) -> None:
        """Press the button."""
        _LOGGER.info("The button has been pressed")


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
