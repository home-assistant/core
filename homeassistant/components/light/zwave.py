"""
Support for Z-Wave lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.zwave/
"""
import logging

from threading import Timer
from homeassistant.components.light import (
    ATTR_WHITE_VALUE, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR,
    ATTR_TRANSITION, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_COLOR,
    SUPPORT_TRANSITION, SUPPORT_WHITE_VALUE, DOMAIN, Light)
from homeassistant.components import zwave
from homeassistant.components.zwave import async_setup_platform  # noqa pylint: disable=unused-import
from homeassistant.const import STATE_OFF, STATE_ON
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

AEOTEC = 0x86
AEOTEC_ZW098_LED_BULB = 0x62
AEOTEC_ZW098_LED_BULB_LIGHT = (AEOTEC, AEOTEC_ZW098_LED_BULB)

COLOR_CHANNEL_WARM_WHITE = 0x01
COLOR_CHANNEL_COLD_WHITE = 0x02
COLOR_CHANNEL_RED = 0x04
COLOR_CHANNEL_GREEN = 0x08
COLOR_CHANNEL_BLUE = 0x10

WORKAROUND_ZW098 = 'zw098'

DEVICE_MAPPINGS = {
    AEOTEC_ZW098_LED_BULB_LIGHT: WORKAROUND_ZW098
}

# Generate midpoint color temperatures for bulbs that have limited
# support for white light colors
TEMP_COLOR_MAX = 500  # mireds (inverted)
TEMP_COLOR_MIN = 154
TEMP_MID_HASS = (TEMP_COLOR_MAX - TEMP_COLOR_MIN) / 2 + TEMP_COLOR_MIN
TEMP_WARM_HASS = (TEMP_COLOR_MAX - TEMP_COLOR_MIN) / 3 * 2 + TEMP_COLOR_MIN
TEMP_COLD_HASS = (TEMP_COLOR_MAX - TEMP_COLOR_MIN) / 3 + TEMP_COLOR_MIN


def get_device(node, values, node_config, **kwargs):
    """Create Z-Wave entity device."""
    refresh = node_config.get(zwave.CONF_REFRESH_VALUE)
    delay = node_config.get(zwave.CONF_REFRESH_DELAY)
    _LOGGER.debug("node=%d value=%d node_config=%s CONF_REFRESH_VALUE=%s"
                  " CONF_REFRESH_DELAY=%s", node.node_id,
                  values.primary.value_id, node_config, refresh, delay)

    if node.has_command_class(zwave.const.COMMAND_CLASS_SWITCH_COLOR):
        return ZwaveColorLight(values, refresh, delay)
    return ZwaveDimmer(values, refresh, delay)


def brightness_state(value):
    """Return the brightness and state."""
    if value.data > 0:
        return round((value.data / 99) * 255), STATE_ON
    return 0, STATE_OFF


def ct_to_hs(temp):
    """Convert color temperature (mireds) to hs."""
    colorlist = list(
        color_util.color_temperature_to_hs(
            color_util.color_temperature_mired_to_kelvin(temp)))
    return [int(val) for val in colorlist]


class ZwaveDimmer(zwave.ZWaveDeviceEntity, Light):
    """Representation of a Z-Wave dimmer."""

    def __init__(self, values, refresh, delay):
        """Initialize the light."""
        zwave.ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._brightness = None
        self._state = None
        self._supported_features = None
        self._delay = delay
        self._refresh_value = refresh
        self._zw098 = None

        # Enable appropriate workaround flags for our device
        # Make sure that we have values for the key before converting to int
        if (self.node.manufacturer_id.strip() and
                self.node.product_id.strip()):
            specific_sensor_key = (int(self.node.manufacturer_id, 16),
                                   int(self.node.product_id, 16))
            if specific_sensor_key in DEVICE_MAPPINGS:
                if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_ZW098:
                    _LOGGER.debug("AEOTEC ZW098 workaround enabled")
                    self._zw098 = 1

        # Used for value change event handling
        self._refreshing = False
        self._timer = None
        _LOGGER.debug('self._refreshing=%s self.delay=%s',
                      self._refresh_value, self._delay)
        self.value_added()
        self.update_properties()

    def update_properties(self):
        """Update internal properties based on zwave values."""
        # Brightness
        self._brightness, self._state = brightness_state(self.values.primary)

    def value_added(self):
        """Call when a new value is added to this entity."""
        self._supported_features = SUPPORT_BRIGHTNESS
        if self.values.dimming_duration is not None:
            self._supported_features |= SUPPORT_TRANSITION

    def value_changed(self):
        """Call when a value for this entity's node has changed."""
        if self._refresh_value:
            if self._refreshing:
                self._refreshing = False
            else:
                def _refresh_value():
                    """Use timer callback for delayed value refresh."""
                    self._refreshing = True
                    self.values.primary.refresh()

                if self._timer is not None and self._timer.isAlive():
                    self._timer.cancel()

                self._timer = Timer(self._delay, _refresh_value)
                self._timer.start()
                return
        super().value_changed()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def _set_duration(self, **kwargs):
        """Set the transition time for the brightness value.

        Zwave Dimming Duration values:
        0x00      = instant
        0x01-0x7F = 1 second to 127 seconds
        0x80-0xFE = 1 minute to 127 minutes
        0xFF      = factory default
        """
        if self.values.dimming_duration is None:
            if ATTR_TRANSITION in kwargs:
                _LOGGER.debug("Dimming not supported by %s.", self.entity_id)
            return

        if ATTR_TRANSITION not in kwargs:
            self.values.dimming_duration.data = 0xFF
            return

        transition = kwargs[ATTR_TRANSITION]
        if transition <= 127:
            self.values.dimming_duration.data = int(transition)
        elif transition > 7620:
            self.values.dimming_duration.data = 0xFE
            _LOGGER.warning("Transition clipped to 127 minutes for %s.",
                            self.entity_id)
        else:
            minutes = int(transition / 60)
            _LOGGER.debug("Transition rounded to %d minutes for %s.",
                          minutes, self.entity_id)
            self.values.dimming_duration.data = minutes + 0x7F

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._set_duration(**kwargs)

        # Zwave multilevel switches use a range of [0, 99] to control
        # brightness. Level 255 means to set it to previous value.
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = int((self._brightness / 255) * 99)
        else:
            brightness = 255

        if self.node.set_dimmer(self.values.primary.value_id, brightness):
            self._state = STATE_ON

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._set_duration(**kwargs)

        if self.node.set_dimmer(self.values.primary.value_id, 0):
            self._state = STATE_OFF


class ZwaveColorLight(ZwaveDimmer):
    """Representation of a Z-Wave color changing light."""

    def __init__(self, values, refresh, delay):
        """Initialize the light."""
        self._color_channels = None
        self._hs = None
        self._ct = None
        self._white = None

        super().__init__(values, refresh, delay)

    def value_added(self):
        """Call when a new value is added to this entity."""
        super().value_added()

        self._supported_features |= SUPPORT_COLOR
        if self._zw098:
            self._supported_features |= SUPPORT_COLOR_TEMP
        elif self._color_channels is not None and self._color_channels & (
                COLOR_CHANNEL_WARM_WHITE | COLOR_CHANNEL_COLD_WHITE):
            self._supported_features |= SUPPORT_WHITE_VALUE

    def update_properties(self):
        """Update internal properties based on zwave values."""
        super().update_properties()

        if self.values.color is None:
            return
        if self.values.color_channels is None:
            return

        # Color Channels
        self._color_channels = self.values.color_channels.data

        # Color Data String
        data = self.values.color.data

        # RGB is always present in the openzwave color data string.
        rgb = [
            int(data[1:3], 16),
            int(data[3:5], 16),
            int(data[5:7], 16)]
        self._hs = color_util.color_RGB_to_hs(*rgb)

        # Parse remaining color channels. Openzwave appends white channels
        # that are present.
        index = 7

        # Warm white
        if self._color_channels & COLOR_CHANNEL_WARM_WHITE:
            warm_white = int(data[index:index+2], 16)
            index += 2
        else:
            warm_white = 0

        # Cold white
        if self._color_channels & COLOR_CHANNEL_COLD_WHITE:
            cold_white = int(data[index:index+2], 16)
            index += 2
        else:
            cold_white = 0

        # Color temperature. With the AEOTEC ZW098 bulb, only two color
        # temperatures are supported. The warm and cold channel values
        # indicate brightness for warm/cold color temperature.
        if self._zw098:
            if warm_white > 0:
                self._ct = TEMP_WARM_HASS
                self._hs = ct_to_hs(self._ct)
            elif cold_white > 0:
                self._ct = TEMP_COLD_HASS
                self._hs = ct_to_hs(self._ct)
            else:
                # RGB color is being used. Just report midpoint.
                self._ct = TEMP_MID_HASS

        elif self._color_channels & COLOR_CHANNEL_WARM_WHITE:
            self._white = warm_white

        elif self._color_channels & COLOR_CHANNEL_COLD_WHITE:
            self._white = cold_white

        # If no rgb channels supported, report None.
        if not (self._color_channels & COLOR_CHANNEL_RED or
                self._color_channels & COLOR_CHANNEL_GREEN or
                self._color_channels & COLOR_CHANNEL_BLUE):
            self._hs = None

    @property
    def hs_color(self):
        """Return the hs color."""
        return self._hs

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return self._white

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self._ct

    def turn_on(self, **kwargs):
        """Turn the device on."""
        rgbw = None

        if ATTR_WHITE_VALUE in kwargs:
            self._white = kwargs[ATTR_WHITE_VALUE]

        if ATTR_COLOR_TEMP in kwargs:
            # Color temperature. With the AEOTEC ZW098 bulb, only two color
            # temperatures are supported. The warm and cold channel values
            # indicate brightness for warm/cold color temperature.
            if self._zw098:
                if kwargs[ATTR_COLOR_TEMP] > TEMP_MID_HASS:
                    self._ct = TEMP_WARM_HASS
                    rgbw = '#000000ff00'
                else:
                    self._ct = TEMP_COLD_HASS
                    rgbw = '#00000000ff'
        elif ATTR_HS_COLOR in kwargs:
            self._hs = kwargs[ATTR_HS_COLOR]
            if ATTR_WHITE_VALUE not in kwargs:
                # white LED must be off in order for color to work
                self._white = 0

        if ATTR_WHITE_VALUE in kwargs or ATTR_HS_COLOR in kwargs:
            rgbw = '#'
            for colorval in color_util.color_hs_to_RGB(*self._hs):
                rgbw += format(colorval, '02x')
            if self._white is not None:
                rgbw += format(self._white, '02x') + '00'
            else:
                rgbw += '0000'

        if rgbw and self.values.color:
            self.values.color.data = rgbw

        super().turn_on(**kwargs)
