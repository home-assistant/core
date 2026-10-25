"""Common test utilities for binary_sensor entity component tests."""

from pytest_homeassistant.common import MockEntity

from homeassistant.components.binary_sensor import BinarySensorEntity


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
