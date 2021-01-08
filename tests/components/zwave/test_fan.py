"""Test Z-Wave fans."""
from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
)
from homeassistant.components.zwave import fan

from tests.mock.zwave import MockEntityValues, MockNode, MockValue, value_changed


def test_get_device_detects_fan(mock_openzwave):
    """Test get_device returns a zwave fan."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockEntityValues(primary=value)

    device = fan.get_device(node=node, values=values, node_config={})
    assert isinstance(device, fan.ZwaveFan)
    assert device.supported_features == SUPPORT_SET_SPEED
    assert device.speed_list == [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]


def test_fan_turn_on(mock_openzwave):
    """Test turning on a zwave fan."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockEntityValues(primary=value)
    device = fan.get_device(node=node, values=values, node_config={})

    device.turn_on()

    assert node.set_dimmer.called
    value_id, brightness = node.set_dimmer.mock_calls[0][1]
    assert value_id == value.value_id
    assert brightness == 255

    node.reset_mock()

    device.turn_on(speed=SPEED_OFF)

    assert node.set_dimmer.called
    value_id, brightness = node.set_dimmer.mock_calls[0][1]

    assert value_id == value.value_id
    assert brightness == 0

    node.reset_mock()

    device.turn_on(speed=SPEED_LOW)

    assert node.set_dimmer.called
    value_id, brightness = node.set_dimmer.mock_calls[0][1]

    assert value_id == value.value_id
    assert brightness == 1

    node.reset_mock()

    device.turn_on(speed=SPEED_MEDIUM)

    assert node.set_dimmer.called
    value_id, brightness = node.set_dimmer.mock_calls[0][1]

    assert value_id == value.value_id
    assert brightness == 50

    node.reset_mock()

    device.turn_on(speed=SPEED_HIGH)

    assert node.set_dimmer.called
    value_id, brightness = node.set_dimmer.mock_calls[0][1]

    assert value_id == value.value_id
    assert brightness == 99


def test_fan_turn_off(mock_openzwave):
    """Test turning off a dimmable zwave fan."""
    node = MockNode()
    value = MockValue(data=46, node=node)
    values = MockEntityValues(primary=value)
    device = fan.get_device(node=node, values=values, node_config={})

    device.turn_off()

    assert node.set_dimmer.called
    value_id, brightness = node.set_dimmer.mock_calls[0][1]
    assert value_id == value.value_id
    assert brightness == 0


def test_fan_value_changed(mock_openzwave):
    """Test value changed for zwave fan."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockEntityValues(primary=value)
    device = fan.get_device(node=node, values=values, node_config={})

    assert not device.is_on

    value.data = 10
    value_changed(value)

    assert device.is_on
    assert device.speed == SPEED_LOW

    value.data = 50
    value_changed(value)

    assert device.is_on
    assert device.speed == SPEED_MEDIUM

    value.data = 90
    value_changed(value)

    assert device.is_on
    assert device.speed == SPEED_HIGH
