"""Test pi_hole sensor."""

from homeassistant.components.pi_hole import PiHoleData
from homeassistant.components.pi_hole.sensor import PiHoleSensor, SENSOR_DICT
from unittest.mock import patch


def test_sensor_class_init(hass):
    """Test that a sensor is constructed correctly."""
    data = PiHoleData(None, "Test Pi-Hole")
    with patch.dict(SENSOR_DICT, {"test": ["Test", "widgets", "mdi:test"]}):
        sensor = PiHoleSensor(data, "test")

        assert sensor.name == "Test Pi-Hole Test"
