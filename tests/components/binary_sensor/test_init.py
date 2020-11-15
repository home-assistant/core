"""The tests for the Binary sensor component."""
from unittest import mock

from homeassistant.components import binary_sensor
from homeassistant.const import STATE_OFF, STATE_ON


def test_state():
    """Test binary sensor state."""
    sensor = binary_sensor.BinarySensorEntity()
    assert STATE_OFF == sensor.state
    with mock.patch(
        "homeassistant.components.binary_sensor.BinarySensorEntity.is_on",
        new=False,
    ):
        assert STATE_OFF == binary_sensor.BinarySensorEntity().state
    with mock.patch(
        "homeassistant.components.binary_sensor.BinarySensorEntity.is_on",
        new=True,
    ):
        assert STATE_ON == binary_sensor.BinarySensorEntity().state


def test_deprecated_base_class(caplog):
    """Test deprecated base class."""

    class CustomBinarySensor(binary_sensor.BinarySensorDevice):
        pass

    CustomBinarySensor()
    assert "BinarySensorDevice is deprecated, modify CustomBinarySensor" in caplog.text
