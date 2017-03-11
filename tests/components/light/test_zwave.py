"""Test Z-Wave lights."""
from homeassistant.components.zwave import const
from homeassistant.components.light import zwave, ATTR_BRIGHTNESS

from tests.mock.zwave import MockNode, MockValue, value_changed


def test_get_device_detects_dimmer(mock_openzwave):
    """Test get_device returns a color light."""
    node = MockNode()
    value = MockValue(data=0, node=node)

    device = zwave.get_device(node, value, {})
    assert isinstance(device, zwave.ZwaveDimmer)


def test_get_device_detects_colorlight(mock_openzwave):
    """Test get_device returns a color light."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)

    device = zwave.get_device(node, value, {})
    assert isinstance(device, zwave.ZwaveColorLight)


def test_dimmer_turn_on(mock_openzwave):
    """Test turning on a dimmable Z-Wave light."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    device = zwave.get_device(node, value, {})

    device.turn_on()

    assert node.set_dimmer.called
    value_id, brightness = node.set_dimmer.mock_calls[0][1]
    assert value_id == value.value_id
    assert brightness == 255

    node.reset_mock()

    device.turn_on(**{ATTR_BRIGHTNESS: 120})

    assert node.set_dimmer.called
    value_id, brightness = node.set_dimmer.mock_calls[0][1]

    assert value_id == value.value_id
    assert brightness == 46  # int(120 / 255 * 99)


def test_dimmer_value_changed(mock_openzwave):
    """Test value changed for dimmer lights."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    device = zwave.get_device(node, value, {})

    assert not device.is_on

    value.data = 46
    value_changed(value)

    assert device.is_on
    assert device.brightness == 118
