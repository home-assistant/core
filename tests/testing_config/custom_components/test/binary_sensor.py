"""
Provide a mock binary sensor platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.binary_sensor import DEVICE_CLASSES, BinarySensorEntity

from tests.common import MockEntity

ENTITIES = {}


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        {}
        if empty
        else {
            device_class: MockBinarySensor(
                name=f"{device_class} sensor",
                is_on=True,
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


class MockBinarySensor(MockEntity, BinarySensorEntity):
    """Mock Binary Sensor class."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._handle("is_on")

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._handle("device_class")
