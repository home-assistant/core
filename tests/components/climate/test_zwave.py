"""Test Z-Wave climate devices."""
import pytest

from homeassistant.components.climate import zwave
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE)

from tests.mock.zwave import (
    MockNode, MockValue, MockEntityValues, value_changed)


@pytest.fixture
def device(hass, mock_openzwave):
    """Fixture to provide a precreated climate device."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(data=1, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        mode=MockValue(data='test1', data_items=[0, 1, 2], node=node),
        fan_mode=MockValue(data='test2', data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data=6, node=node),
        fan_state=MockValue(data=7, node=node),
    )
    device = zwave.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_zxt_120(hass, mock_openzwave):
    """Fixture to provide a precreated climate device."""
    node = MockNode(manufacturer_id='5254', product_id='8377')

    values = MockEntityValues(
        primary=MockValue(data=1, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        mode=MockValue(data='test1', data_items=[0, 1, 2], node=node),
        fan_mode=MockValue(data='test2', data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data=6, node=node),
        fan_state=MockValue(data=7, node=node),
        zxt_120_swing_mode=MockValue(
            data='test3', data_items=[6, 7, 8], node=node),
    )
    device = zwave.get_device(hass, node=node, values=values, node_config={})

    yield device


def test_zxt_120_swing_mode(device_zxt_120):
    """Test operation of the zxt 120 swing mode."""
    device = device_zxt_120

    assert device.swing_list == [6, 7, 8]
    assert device._zxt_120 == 1

    # Test set mode
    assert device.values.zxt_120_swing_mode.data == 'test3'
    device.set_swing_mode('test_swing_set')
    assert device.values.zxt_120_swing_mode.data == 'test_swing_set'

    # Test mode changed
    value_changed(device.values.zxt_120_swing_mode)
    assert device.current_swing_mode == 'test_swing_set'
    device.values.zxt_120_swing_mode.data = 'test_swing_updated'
    value_changed(device.values.zxt_120_swing_mode)
    assert device.current_swing_mode == 'test_swing_updated'


def test_temperature_unit(device):
    """Test temperature unit."""
    assert device.temperature_unit == TEMP_CELSIUS
    device.values.temperature.units = 'F'
    value_changed(device.values.temperature)
    assert device.temperature_unit == TEMP_FAHRENHEIT
    device.values.temperature.units = 'C'
    value_changed(device.values.temperature)
    assert device.temperature_unit == TEMP_CELSIUS


def test_default_target_temperature(device):
    """Test default setting of target temperature."""
    assert device.target_temperature == 1
    device.values.primary.data = 0
    value_changed(device.values.primary)
    assert device.target_temperature == 5  # Current Temperature


def test_data_lists(device):
    """Test data lists from zwave value items."""
    assert device.fan_list == [3, 4, 5]
    assert device.operation_list == [0, 1, 2]


def test_target_value_set(device):
    """Test values changed for climate device."""
    assert device.values.primary.data == 1
    device.set_temperature()
    assert device.values.primary.data == 1
    device.set_temperature(**{
        ATTR_TEMPERATURE: 2
    })
    assert device.values.primary.data == 2


def test_operation_value_set(device):
    """Test values changed for climate device."""
    assert device.values.mode.data == 'test1'
    device.set_operation_mode('test_set')
    assert device.values.mode.data == 'test_set'


def test_fan_mode_value_set(device):
    """Test values changed for climate device."""
    assert device.values.fan_mode.data == 'test2'
    device.set_fan_mode('test_fan_set')
    assert device.values.fan_mode.data == 'test_fan_set'


def test_target_value_changed(device):
    """Test values changed for climate device."""
    assert device.target_temperature == 1
    device.values.primary.data = 2
    value_changed(device.values.primary)
    assert device.target_temperature == 2


def test_temperature_value_changed(device):
    """Test values changed for climate device."""
    assert device.current_temperature == 5
    device.values.temperature.data = 3
    value_changed(device.values.temperature)
    assert device.current_temperature == 3


def test_operation_value_changed(device):
    """Test values changed for climate device."""
    assert device.current_operation == 'test1'
    device.values.mode.data = 'test_updated'
    value_changed(device.values.mode)
    assert device.current_operation == 'test_updated'


def test_fan_mode_value_changed(device):
    """Test values changed for climate device."""
    assert device.current_fan_mode == 'test2'
    device.values.fan_mode.data = 'test_updated_fan'
    value_changed(device.values.fan_mode)
    assert device.current_fan_mode == 'test_updated_fan'


def test_operating_state_value_changed(device):
    """Test values changed for climate device."""
    assert device.device_state_attributes[zwave.ATTR_OPERATING_STATE] == 6
    device.values.operating_state.data = 8
    value_changed(device.values.operating_state)
    assert device.device_state_attributes[zwave.ATTR_OPERATING_STATE] == 8


def test_fan_state_value_changed(device):
    """Test values changed for climate device."""
    assert device.device_state_attributes[zwave.ATTR_FAN_STATE] == 7
    device.values.fan_state.data = 9
    value_changed(device.values.fan_state)
    assert device.device_state_attributes[zwave.ATTR_FAN_STATE] == 9
