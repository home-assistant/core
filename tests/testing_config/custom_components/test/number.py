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

    _attr_value = None

    @property
    def max(self) -> list:
        """Return the maximum accepted value (inclusive)."""
        return self._handle("max")

    @property
    def min(self) -> list:
        """Return the minimum accepted value (inclusive)."""
        return self._handle("min")

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
                name="number 1",
                unique_id=UNIQUE_NUMBER,
                value=50.0,
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
