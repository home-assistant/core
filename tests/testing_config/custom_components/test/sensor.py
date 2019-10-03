"""
Provide a mock sensor platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.sensor import DEVICE_CLASSES
from tests.common import MockEntity


ENTITIES = {}


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        {}
        if empty
        else {
            device_class: MockSensor(
                name=f"{device_class} sensor",
                unique_id=f"unique_{device_class}",
                device_class=device_class,
            )
            for device_class in DEVICE_CLASSES
        }
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(list(ENTITIES.values()))


class MockSensor(MockEntity):
    """Mock Sensor class."""

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._handle("device_class")
