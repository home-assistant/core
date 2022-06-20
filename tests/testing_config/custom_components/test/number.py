"""
Provide a mock number platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.number import NumberEntity

from tests.common import MockEntity

UNIQUE_NUMBER = "unique_number"

ENTITIES = []


class MockNumberEntity(MockEntity, NumberEntity):
    """Mock number class."""

    @property
    def native_max_value(self):
        """Return the native native_max_value."""
        return self._handle("native_max_value")

    @property
    def native_min_value(self):
        """Return the native native_min_value."""
        return self._handle("native_min_value")

    @property
    def native_step(self):
        """Return the native native_step."""
        return self._handle("native_step")

    @property
    def native_unit_of_measurement(self):
        """Return the native unit_of_measurement."""
        return self._handle("native_unit_of_measurement")

    @property
    def native_value(self):
        """Return the native value of this sensor."""
        return self._handle("native_value")

    def set_native_value(self, value: float) -> None:
        """Change the selected option."""
        self._values["native_value"] = value


class LegacyMockNumberEntity(MockEntity, NumberEntity):
    """Mock Number class using deprecated features."""

    @property
    def max_value(self):
        """Return the native max_value."""
        return self._handle("max_value")

    @property
    def min_value(self):
        """Return the native min_value."""
        return self._handle("min_value")

    @property
    def step(self):
        """Return the native step."""
        return self._handle("step")

    @property
    def value(self):
        """Return the current value."""
        return self._handle("value")

    def set_value(self, value: float) -> None:
        """Change the selected option."""
        self._values["value"] = value


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
                native_value=50.0,
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
