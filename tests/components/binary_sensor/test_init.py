"""The tests for the Binary sensor component."""
from unittest import mock

from homeassistant.components import binary_sensor
from homeassistant.const import STATE_OFF, STATE_ON


def test_state():
    """Test binary sensor state."""
    sensor = binary_sensor.BinarySensorEntity()
    assert sensor.state is None
    with mock.patch(
        "homeassistant.components.binary_sensor.BinarySensorEntity.is_on",
        new=False,
    ):
        assert binary_sensor.BinarySensorEntity().state == STATE_OFF
    with mock.patch(
        "homeassistant.components.binary_sensor.BinarySensorEntity.is_on",
        new=True,
    ):
        assert binary_sensor.BinarySensorEntity().state == STATE_ON
