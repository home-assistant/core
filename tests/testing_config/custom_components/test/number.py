"""
Provide a mock number platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.number import NumberEntity

from tests.common import MockEntity

UNIQUE_SELECT_1 = "unique_number_1"
UNIQUE_SELECT_2 = "unique_number_2"

ENTITIES = []


class MockSelectEntity(MockEntity, NumberEntity):
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
            MockSelectEntity(
                name="number 1",
                unique_id="unique_number_1",
                min=0.0,
                max=100.0,
                value=50.0,
            ),
            MockSelectEntity(
                name="number 2",
                unique_id="unique_number_2",
                min=0.0,
                max=1.0,
                value=0.5,
                step=0.1,
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
