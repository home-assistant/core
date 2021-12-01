"""
Provide a mock number platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.number import NumberEntity

from tests.common import MockEntity

UNIQUE_NUMBER = "unique_number"

ENTITIES = []


class MockNumberEntity(MockEntity, NumberEntity):
    """Mock Select class."""

    _attr_value = 50.0
    _attr_step = 1.0

    @property
    def value(self):
        """Return the current value."""
        return self._handle("value")

    def set_value(self, value: float) -> None:
        """Change the selected option."""
        self._attr_value = value


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockNumberEntity(
                name="test",
                unique_id=UNIQUE_NUMBER,
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
