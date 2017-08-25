"""Test Z-Wave lights."""
from unittest.mock import patch, MagicMock

import homeassistant.components.zwave
from homeassistant.components.zwave import const
from homeassistant.components.light import (
    zwave, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS, SUPPORT_TRANSITION, SUPPORT_RGB_COLOR,
    SUPPORT_COLOR_TEMP)

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
    assert device.supported_features == SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR


def test_get_device_detects_zw098(mock_openzwave):
    """Test get_device returns a zw098 color light."""
    node = MockNode(manufacturer_id='0086', product_id='0062',
                    command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    values = MockLightValues(primary=value)
    device = zwave.get_device(node=node, values=values, node_config={})
    assert isinstance(device, zwave.ZwaveColorLight)
    assert device.supported_features == (
        SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR | SUPPORT_COLOR_TEMP)


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


def test_set_rgb_color(mock_openzwave):
    """Test setting zwave light color."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Suppoorts RGB only
    color_channels = MockValue(data=0x1c, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert color.data == '#0000000000'

    device.turn_on(**{ATTR_RGB_COLOR: (200, 150, 100)})

    assert color.data == '#c896640000'


def test_set_rgbw_color(mock_openzwave):
    """Test setting zwave light color."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Suppoorts RGBW
    color_channels = MockValue(data=0x1d, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert color.data == '#0000000000'

    device.turn_on(**{ATTR_RGB_COLOR: (200, 150, 100)})

    assert color.data == '#c86400c800'


def test_zw098_set_color_temp(mock_openzwave):
    """Test setting zwave light color."""
    node = MockNode(manufacturer_id='0086', product_id='0062',
                    command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Suppoorts RGB, warm white, cold white
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
    # Suppoorts color temperature only
    color_channels = MockValue(data=0x01, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.rgb_color is None


def test_no_color_value(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    values = MockLightValues(primary=value)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.rgb_color is None


def test_no_color_channels_value(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    values = MockLightValues(primary=value, color=color)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.rgb_color is None


def test_rgb_value_changed(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Suppoorts RGB only
    color_channels = MockValue(data=0x1c, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.rgb_color == [0, 0, 0]

    color.data = '#c896640000'
    value_changed(color)

    assert device.rgb_color == [200, 150, 100]


def test_rgbww_value_changed(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Suppoorts RGB, Warm White
    color_channels = MockValue(data=0x1d, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.rgb_color == [0, 0, 0]

    color.data = '#c86400c800'
    value_changed(color)

    assert device.rgb_color == [200, 150, 100]


def test_rgbcw_value_changed(mock_openzwave):
    """Test value changed for rgb lights."""
    node = MockNode(command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Suppoorts RGB, Cold White
    color_channels = MockValue(data=0x1e, node=node)
    values = MockLightValues(primary=value, color=color,
                             color_channels=color_channels)
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.rgb_color == [0, 0, 0]

    color.data = '#c86400c800'
    value_changed(color)

    assert device.rgb_color == [200, 150, 100]


def test_ct_value_changed(mock_openzwave):
    """Test value changed for zw098 lights."""
    node = MockNode(manufacturer_id='0086', product_id='0062',
                    command_classes=[const.COMMAND_CLASS_SWITCH_COLOR])
    value = MockValue(data=0, node=node)
    color = MockValue(data='#0000000000', node=node)
    # Suppoorts RGB, Cold White
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
