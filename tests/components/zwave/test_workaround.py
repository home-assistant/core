"""Test Z-Wave workarounds."""
from homeassistant.components.zwave import const, workaround
from tests.mock.zwave import MockNode, MockValue


def test_get_device_no_component_mapping():
    """Test that None is returned."""
    node = MockNode(manufacturer_id=' ')
    value = MockValue(data=0, node=node)
    assert workaround.get_device_component_mapping(value) is None


def test_get_device_component_mapping():
    """Test that component is returned."""
    node = MockNode(manufacturer_id='010f', product_type='0b00')
    value = MockValue(data=0, node=node,
                      command_class=const.COMMAND_CLASS_SENSOR_ALARM)
    assert workaround.get_device_component_mapping(value) == 'binary_sensor'


def test_get_device_no_mapping():
    """Test that no device mapping is returned."""
    node = MockNode(manufacturer_id=' ')
    value = MockValue(data=0, node=node)
    assert workaround.get_device_mapping(value) is None


def test_get_device_mapping_mt():
    """Test that device mapping mt is returned."""
    node = MockNode(manufacturer_id='0047', product_type='5a52')
    value = MockValue(data=0, node=node)
    assert workaround.get_device_mapping(value) == 'workaround_no_position'


def test_get_device_mapping_mtii():
    """Test that device mapping mtii is returned."""
    node = MockNode(manufacturer_id='013c', product_type='0002',
                    product_id='0002')
    value = MockValue(data=0, node=node, index=0)
    assert workaround.get_device_mapping(value) == 'trigger_no_off_event'
