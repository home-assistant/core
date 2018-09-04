"""Test Z-Wave sensor."""
from homeassistant.components.sensor import zwave
from homeassistant.components.zwave import const
import homeassistant.const

from tests.mock.zwave import (
   MockNode, MockValue, MockEntityValues, value_changed)


def test_get_device_detects_none(mock_openzwave):
    """Test get_device returns None."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert device is None


def test_get_device_detects_alarmsensor(mock_openzwave):
    """Test get_device returns a Z-Wave alarmsensor."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_ALARM,
                                     const.COMMAND_CLASS_SENSOR_ALARM])
    value = MockValue(data=0, node=node)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert isinstance(device, zwave.ZWaveAlarmSensor)


def test_get_device_detects_multilevelsensor(mock_openzwave):
    """Test get_device returns a Z-Wave multilevel sensor."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SENSOR_MULTILEVEL,
                                     const.COMMAND_CLASS_METER])
    value = MockValue(data=0, node=node)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert isinstance(device, zwave.ZWaveMultilevelSensor)
    assert device.force_update


def test_get_device_detects_multilevel_meter(mock_openzwave):
    """Test get_device returns a Z-Wave multilevel sensor."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_METER])
    value = MockValue(data=0, node=node, type=const.TYPE_DECIMAL)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert isinstance(device, zwave.ZWaveMultilevelSensor)


def test_multilevelsensor_value_changed_temp_fahrenheit(mock_openzwave):
    """Test value changed for Z-Wave multilevel sensor for temperature."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SENSOR_MULTILEVEL,
                                     const.COMMAND_CLASS_METER])
    value = MockValue(data=190.95555, units='F', node=node)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert device.state == 191.0
    assert device.unit_of_measurement == homeassistant.const.TEMP_FAHRENHEIT
    value.data = 197.95555
    value_changed(value)
    assert device.state == 198.0


def test_multilevelsensor_value_changed_temp_celsius(mock_openzwave):
    """Test value changed for Z-Wave multilevel sensor for temperature."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SENSOR_MULTILEVEL,
                                     const.COMMAND_CLASS_METER])
    value = MockValue(data=38.85555, units='C', node=node)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert device.state == 38.9
    assert device.unit_of_measurement == homeassistant.const.TEMP_CELSIUS
    value.data = 37.95555
    value_changed(value)
    assert device.state == 38.0


def test_multilevelsensor_value_changed_other_units(mock_openzwave):
    """Test value changed for Z-Wave multilevel sensor for other units."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SENSOR_MULTILEVEL,
                                     const.COMMAND_CLASS_METER])
    value = MockValue(data=190.95555, units='kWh', node=node)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert device.state == 190.96
    assert device.unit_of_measurement == 'kWh'
    value.data = 197.95555
    value_changed(value)
    assert device.state == 197.96


def test_multilevelsensor_value_changed_integer(mock_openzwave):
    """Test value changed for Z-Wave multilevel sensor for other units."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SENSOR_MULTILEVEL,
                                     const.COMMAND_CLASS_METER])
    value = MockValue(data=5, units='counts', node=node)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert device.state == 5
    assert device.unit_of_measurement == 'counts'
    value.data = 6
    value_changed(value)
    assert device.state == 6


def test_alarm_sensor_value_changed(mock_openzwave):
    """Test value changed for Z-Wave sensor."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_ALARM,
                                     const.COMMAND_CLASS_SENSOR_ALARM])
    value = MockValue(data=12.34, node=node, units='%')
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert device.state == 12.34
    assert device.unit_of_measurement == '%'
    value.data = 45.67
    value_changed(value)
    assert device.state == 45.67
