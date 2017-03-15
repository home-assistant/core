"""Test Z-Wave sensor."""
from homeassistant.components.sensor import zwave
from homeassistant.components.zwave import const
from tests.mock.zwave import (
   MockNode, MockValue, MockEntityValues, value_changed)


def test_get_device_detects_sensor(mock_openzwave):
    """Test get_device returns a Z-Wave Sensor."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_BATTERY])
    value = MockValue(data=0, command_class=const.COMMAND_CLASS_BATTERY,
                      node=node)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert isinstance(device, zwave.ZWaveSensor)


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


def test_multilevelsensor_value_changed_temp_units(mock_openzwave):
    """Test value changed for Z-Wave multilevel sensor for temperature."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SENSOR_MULTILEVEL,
                                     const.COMMAND_CLASS_METER])
    value = MockValue(data=190.95555, units='F', node=node)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert device.state == 191.0
    assert value.units == 'F'
    value.data = 197.95555
    value_changed(value)
    assert device.state == 198.0


def test_multilevelsensor_value_changed_other_units(mock_openzwave):
    """Test value changed for Z-Wave multilevel sensor for other units."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SENSOR_MULTILEVEL,
                                     const.COMMAND_CLASS_METER])
    value = MockValue(data=190.95555, units='kWh', node=node)
    values = MockEntityValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert device.state == 190.96
    assert value.units == 'kWh'
    value.data = 197.95555
    value_changed(value)
    assert device.state == 197.96
