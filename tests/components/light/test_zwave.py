"""Test Z-Wave lights."""
from unittest.mock import patch, MagicMock

import homeassistant.components.zwave
from homeassistant.components.zwave import const
from homeassistant.components.light import (
    zwave, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS, SUPPORT_TRANSITION, SUPPORT_COLOR, ATTR_WHITE_VALUE,
    SUPPORT_COLOR_TEMP, SUPPORT_WHITE_VALUE)

from tests.mock.zwave import (
    MockNode, MockValue, MockEntityValues, value_changed)


class MockLightValues(MockEntityValues):
    """Mock Z-Wave light values."""

    def __init__(self, **kwargs):
        """Initialize the mock zwave values."""
        self.dimming_duration = None
        self.color = None
        self.color_channels = None
        super().__init__(**kwargs)


def test_get_device_detects_dimmer(mock_openzwave):
    """Test get_device returns a normal dimmer."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockLightValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert isinstance(device, zwave.ZwaveDimmer)
    assert device.supported_features == SUPPORT_BRIGHTNESS


def test_get_device_detects_colorlight(mock_openzwave):
    """Test get_device returns a color light."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    values = MockLightValues(primary=value)

    device = zwave.get_device(node=node, values=values, node_config={})
    assert isinstance(device, zwave.ZwaveColorLight)
    assert device.supported_features == SUPPORT_BRIGHTNESS | SUPPORT_COLOR


def test_get_device_detects_zw098(mock_openzwave):
    """Test get_device returns a zw098 color light."""
    node = MockNode(manufacturer_id='0086', product_id='0062',
                    command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    values = MockLightValues(primary=value)
    device = zwave.get_device(node=node, values=values, node_config={})
    assert isinstance(device, zwave.ZwaveColorLight)
    assert device.supported_features == (
        SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_COLOR_TEMP)


def test_get_device_detects_rgbw_light(mock_openzwave):
    """Test get_device returns a color light."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    color_channels = MockValue(data=0x1d, node=node)
    values = MockLightValues(
        primary=value, color=color, color_channels=color_channels)

    device = zwave.get_device(node=node, values=values, node_config={})
    device.value_added()
    assert isinstance(device, zwave.ZwaveColorLight)
    assert device.supported_features == (
        SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_WHITE_VALUE)


def test_dimmer_turn_on(mock_openzwave):
    """Test turning on a dimmable Z-Wave light."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockLightValues(primary=value)
    device = zwave.get_device(node=node, values=values, node_config={})

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

    with patch.object(zwave, '_LOGGER', MagicMock()) as mock_logger:
        device.turn_on(**{ATTR_TRANSITION: 35})
        assert mock_logger.debug.called
        assert node.set_dimmer.called
        msg, entity_id = mock_logger.debug.mock_calls[0][1]
        assert entity_id == device.entity_id


def test_dimmer_transitions(mock_openzwave):
    """Test dimming transition on a dimmable Z-Wave light."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    duration = MockValue(data=0, node=node)
    values = MockLightValues(primary=value, dimming_duration=duration)
    device = zwave.get_device(node=node, values=values, node_config={})
    assert device.supported_features == SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION

    # Test turn_on
    # Factory Default
    device.turn_on()
    assert duration.data == 0xFF

    # Seconds transition
    device.turn_on(**{ATTR_TRANSITION: 45})
    assert duration.data == 45

    # Minutes transition
    device.turn_on(**{ATTR_TRANSITION: 245})
    assert duration.data == 0x83

    # Clipped transition
    device.turn_on(**{ATTR_TRANSITION: 10000})
    assert duration.data == 0xFE

    # Test turn_off
    # Factory Default
    device.turn_off()
    assert duration.data == 0xFF

    # Seconds transition
    device.turn_off(**{ATTR_TRANSITION: 45})
    assert duration.data == 45

    # Minutes transition
    device.turn_off(**{ATTR_TRANSITION: 245})
    assert duration.data == 0x83

    # Clipped transition
    device.turn_off(**{ATTR_TRANSITION: 10000})
    assert duration.data == 0xFE


def test_dimmer_turn_off(mock_openzwave):
    """Test turning off a dimmable Z-Wave light."""
    node = MockNode()
    value = MockValue(data=46, node=node)
    values = MockLightValues(primary=value)
    device = zwave.get_device(node=node, values=values, node_config={})

    device.turn_off()

    assert node.set_dimmer.called
    value_id, brightness = node.set_dimmer.mock_calls[0][1]
    assert value_id == value.value_id
    assert brightness == 0


def test_dimmer_value_changed(mock_openzwave):
    """Test value changed for dimmer lights."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockLightValues(primary=value)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert not device.is_on

    value.data = 46
    value_changed(value)

    assert device.is_on
    assert device.brightness == 118


def test_dimmer_refresh_value(mock_openzwave):
    """Test value changed for dimmer lights."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockLightValues(primary=value)
    device = zwave.get_device(node=node, values=values, node_config={
        homeassistant.components.zwave.CONF_REFRESH_VALUE: True,
        homeassistant.components.zwave.CONF_REFRESH_DELAY: 5,
    })

    assert not device.is_on

    with patch.object(zwave, 'Timer', MagicMock()) as mock_timer:
        value.data = 46
        value_changed(value)

        assert not device.is_on
        assert mock_timer.called
        assert len(mock_timer.mock_calls) == 2
        timeout, callback = mock_timer.mock_calls[0][1][:2]
        assert timeout == 5
        assert mock_timer().start.called
        assert len(mock_timer().start.mock_calls) == 1

        with patch.object(zwave, 'Timer', MagicMock()) as mock_timer_2:
            value_changed(value)
            assert not device.is_on
            assert mock_timer().cancel.called
            assert len(mock_timer_2.mock_calls) == 2
            timeout, callback = mock_timer_2.mock_calls[0][1][:2]
            assert timeout == 5
            assert mock_timer_2().start.called
            assert len(mock_timer_2().start.mock_calls) == 1

            callback()
            assert device.is_on
            assert device.brightness == 118


def test_set_hs_color(mock_openzwave):
    """Test setting zwave light color."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Supports RGB only
    color_channels = MockValue(data=0x1c, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert color.data == '#0000000000'

    device.turn_on(**{ATTR_HS_COLOR: (30, 50)})

    assert color.data == '#ffbf7f0000'


def test_set_white_value(mock_openzwave):
    """Test setting zwave light color."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Supports RGBW
    color_channels = MockValue(data=0x1d, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert color.data == '#0000000000'

    device.turn_on(**{ATTR_WHITE_VALUE: 200})

    assert color.data == '#ffffffc800'


def test_disable_white_if_set_color(mock_openzwave):
    """
    Test that _white is set to 0 if turn_on with ATTR_HS_COLOR.

    See Issue #13930 - many RGBW ZWave bulbs will only activate the RGB LED to
    produce color if _white is set to zero.
    """
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Supports RGB only
    color_channels = MockValue(data=0x1c, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})
    device._white = 234

    assert color.data == '#0000000000'
    assert device.white_value == 234

    device.turn_on(**{ATTR_HS_COLOR: (30, 50)})

    assert device.white_value == 0
    assert color.data == '#ffbf7f0000'


def test_zw098_set_color_temp(mock_openzwave):
    """Test setting zwave light color."""
    node = MockNode(manufacturer_id='0086', product_id='0062',
                    command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Supports RGB, warm white, cold white
    color_channels = MockValue(data=0x1f, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert color.data == '#0000000000'

    device.turn_on(**{ATTR_COLOR_TEMP: 200})

    assert color.data == '#00000000ff'

    device.turn_on(**{ATTR_COLOR_TEMP: 400})

    assert color.data == '#000000ff00'


def test_rgb_not_supported(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Supports color temperature only
    color_channels = MockValue(data=0x01, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.hs_color is None


def test_no_color_value(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    values = MockLightValues(primary=value)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.hs_color is None


def test_no_color_channels_value(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    values = MockLightValues(primary=value, color=color)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.hs_color is None


def test_rgb_value_changed(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Supports RGB only
    color_channels = MockValue(data=0x1c, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.hs_color == (0, 0)

    color.data = '#ffbf800000'
    value_changed(color)

    assert device.hs_color == (29.764, 49.804)


def test_rgbww_value_changed(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Supports RGB, Warm White
    color_channels = MockValue(data=0x1d, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.hs_color == (0, 0)
    assert device.white_value == 0

    color.data = '#c86400c800'
    value_changed(color)

    assert device.hs_color == (30, 100)
    assert device.white_value == 200


def test_rgbcw_value_changed(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Supports RGB, Cold White
    color_channels = MockValue(data=0x1e, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.hs_color == (0, 0)
    assert device.white_value == 0

    color.data = '#c86400c800'
    value_changed(color)

    assert device.hs_color == (30, 100)
    assert device.white_value == 200


def test_ct_value_changed(mock_openzwave):
    """Test value changed for zw098 lights."""
    node = MockNode(manufacturer_id='0086', product_id='0062',
                    command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Supports RGB, Cold White
    color_channels = MockValue(data=0x1f, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.color_temp == zwave.TEMP_MID_HASS

    color.data = '#000000ff00'
    value_changed(color)

    assert device.color_temp == zwave.TEMP_WARM_HASS

    color.data = '#00000000ff'
    value_changed(color)

    assert device.color_temp == zwave.TEMP_COLD_HASS
