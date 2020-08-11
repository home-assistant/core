"""Test Z-Wave binary sensors."""
import datetime

from homeassistant.components.zwave import binary_sensor, const

from tests.async_mock import patch
from tests.mock.zwave import MockEntityValues, MockNode, MockValue, value_changed


def test_get_device_detects_none(mock_openzwave):
    """Test device is not returned."""
    node = MockNode()
    value = MockValue(data=False, node=node)
    values = MockEntityValues(primary=value)

    device = binary_sensor.get_device(node=node, values=values, node_config={})
    assert device is None


def test_get_device_detects_trigger_sensor(mock_openzwave):
    """Test device is a trigger sensor."""
    node = MockNode(manufacturer_id="013c", product_type="0002", product_id="0002")
    value = MockValue(data=False, node=node)
    values = MockEntityValues(primary=value)

    device = binary_sensor.get_device(node=node, values=values, node_config={})
    assert isinstance(device, binary_sensor.ZWaveTriggerSensor)
    assert device.device_class == "motion"


def test_get_device_detects_workaround_sensor(mock_openzwave):
    """Test that workaround returns a binary sensor."""
    node = MockNode(manufacturer_id="010f", product_type="0b00")
    value = MockValue(
        data=False, node=node, command_class=const.COMMAND_CLASS_SENSOR_ALARM
    )
    values = MockEntityValues(primary=value)

    device = binary_sensor.get_device(node=node, values=values, node_config={})
    assert isinstance(device, binary_sensor.ZWaveBinarySensor)


def test_get_device_detects_sensor(mock_openzwave):
    """Test that device returns a binary sensor."""
    node = MockNode()
    value = MockValue(
        data=False, node=node, command_class=const.COMMAND_CLASS_SENSOR_BINARY
    )
    values = MockEntityValues(primary=value)

    device = binary_sensor.get_device(node=node, values=values, node_config={})
    assert isinstance(device, binary_sensor.ZWaveBinarySensor)


def test_binary_sensor_value_changed(mock_openzwave):
    """Test value changed for binary sensor."""
    node = MockNode()
    value = MockValue(
        data=False, node=node, command_class=const.COMMAND_CLASS_SENSOR_BINARY
    )
    values = MockEntityValues(primary=value)
    device = binary_sensor.get_device(node=node, values=values, node_config={})

    assert not device.is_on

    value.data = True
    value_changed(value)

    assert device.is_on


async def test_trigger_sensor_value_changed(hass, mock_openzwave):
    """Test value changed for trigger sensor."""
    node = MockNode(manufacturer_id="013c", product_type="0002", product_id="0002")
    value = MockValue(data=False, node=node)
    value_off_delay = MockValue(data=15, node=node)
    values = MockEntityValues(primary=value, off_delay=value_off_delay)
    device = binary_sensor.get_device(node=node, values=values, node_config={})

    assert not device.is_on

    value.data = True
    await hass.async_add_job(value_changed, value)
    assert device.invalidate_after is None

    device.hass = hass

    value.data = True
    await hass.async_add_job(value_changed, value)
    assert device.is_on

    test_time = device.invalidate_after - datetime.timedelta(seconds=1)
    with patch("homeassistant.util.dt.utcnow", return_value=test_time):
        assert device.is_on

    test_time = device.invalidate_after
    with patch("homeassistant.util.dt.utcnow", return_value=test_time):
        assert not device.is_on
