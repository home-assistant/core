"""The tests for the Binary sensor component."""
import unittest
from unittest import mock

from homeassistant.components import binary_sensor
from homeassistant.const import STATE_OFF, STATE_ON


class TestBinarySensor(unittest.TestCase):
    """Test the binary_sensor base class."""

    def test_state(self):
        """Test binary sensor state."""
        sensor = binary_sensor.BinarySensorEntity()
        assert STATE_OFF == sensor.state
        with mock.patch(
            "homeassistant.components.binary_sensor.BinarySensorEntity.is_on",
            new=False,
        ):
            assert STATE_OFF == binary_sensor.BinarySensorEntity().state
        with mock.patch(
            "homeassistant.components.binary_sensor.BinarySensorEntity.is_on", new=True,
        ):
            assert STATE_ON == binary_sensor.BinarySensorEntity().state
