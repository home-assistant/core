"""Common test utilities for binary_sensor entity component tests."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from tests.common import MockEntity


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
