"""
Support for Z-Wave lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.zwave/
"""
import logging

# Because we do not compile openzwave on CI
# pylint: disable=import-error
from threading import Timer
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, \
    ATTR_RGB_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, \
    SUPPORT_RGB_COLOR, DOMAIN, Light
from homeassistant.components import zwave
from homeassistant.components.zwave import async_setup_platform  # noqa # pylint: disable=unused-import
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.util.color import HASS_COLOR_MAX, HASS_COLOR_MIN, \
    color_temperature_mired_to_kelvin, color_temperature_to_rgb, \
    color_rgb_to_rgbw, color_rgbw_to_rgb

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
TEMP_MID_HASS = (HASS_COLOR_MAX - HASS_COLOR_MIN) / 2 + HASS_COLOR_MIN
TEMP_WARM_HASS = (HASS_COLOR_MAX - HASS_COLOR_MIN) / 3 * 2 + HASS_COLOR_MIN
TEMP_COLD_HASS = (HASS_COLOR_MAX - HASS_COLOR_MIN) / 3 + HASS_COLOR_MIN

SUPPORT_ZWAVE_DIMMER = SUPPORT_BRIGHTNESS
SUPPORT_ZWAVE_COLOR = SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR
SUPPORT_ZWAVE_COLORTEMP = (SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR
                           | SUPPORT_COLOR_TEMP)


def get_device(node, value, node_config, **kwargs):
    """Create zwave entity device."""
    name = '{}.{}'.format(DOMAIN, zwave.object_id(value))
    refresh = node_config.get(zwave.CONF_REFRESH_VALUE)
    delay = node_config.get(zwave.CONF_REFRESH_DELAY)
    _LOGGER.debug('name=%s node_config=%s CONF_REFRESH_VALUE=%s'
                  ' CONF_REFRESH_DELAY=%s', name, node_config,
                  refresh, delay)

    if node.has_command_class(zwave.const.COMMAND_CLASS_SWITCH_COLOR):
        return ZwaveColorLight(value, refresh, delay)
    else:
        return ZwaveDimmer(value, refresh, delay)


def brightness_state(value):
    """Return the brightness and state."""
    if value.data > 0:
        return round((value.data / 99) * 255, 0), STATE_ON
    else:
        return 0, STATE_OFF


class ZwaveDimmer(zwave.ZWaveDeviceEntity, Light):
    """Representation of a Z-Wave dimmer."""

    def __init__(self, value, refresh, delay):
        """Initialize the light."""
        zwave.ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._brightness = None
        self._state = None
        self._delay = delay
        self._refresh_value = refresh
        self._zw098 = None

        # Enable appropriate workaround flags for our device
        # Make sure that we have values for the key before converting to int
        if (value.node.manufacturer_id.strip() and
                value.node.product_id.strip()):
            specific_sensor_key = (int(value.node.manufacturer_id, 16),
                                   int(value.node.product_id, 16))
            if specific_sensor_key in DEVICE_MAPPINGS:
                if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_ZW098:
                    _LOGGER.debug("AEOTEC ZW098 workaround enabled")
                    self._zw098 = 1

        # Used for value change event handling
        self._refreshing = False
        self._timer = None
        _LOGGER.debug('self._refreshing=%s self.delay=%s',
                      self._refresh_value, self._delay)
        self.update_properties()

    def update_properties(self):
        """Update internal properties based on zwave values."""
        # Brightness
        self._brightness, self._state = brightness_state(self._value)

    def value_changed(self):
        """Called when a value for this entity's node has changed."""
        if self._refresh_value:
            if self._refreshing:
                self._refreshing = False
            else:
                def _refresh_value():
                    """Used timer callback for delayed value refresh."""
                    self._refreshing = True
                    self._value.refresh()

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
        return SUPPORT_ZWAVE_DIMMER

    def turn_on(self, **kwargs):
        """Turn the device on."""
        # Zwave multilevel switches use a range of [0, 99] to control
        # brightness. Level 255 means to set it to previous value.
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = int((self._brightness / 255) * 99)
        else:
            brightness = 255

        if self._value.node.set_dimmer(self._value.value_id, brightness):
            self._state = STATE_ON

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self._value.node.set_dimmer(self._value.value_id, 0):
            self._state = STATE_OFF


def ct_to_rgb(temp):
    """Convert color temperature (mireds) to RGB."""
    colorlist = list(
        color_temperature_to_rgb(color_temperature_mired_to_kelvin(temp)))
    return [int(val) for val in colorlist]


class ZwaveColorLight(ZwaveDimmer):
    """Representation of a Z-Wave color changing light."""

    def __init__(self, value, refresh, delay):
        """Initialize the light."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        self._value_color = None
        self._value_color_channels = None
        self._color_channels = None
        self._rgb = None
        self._ct = None

        super().__init__(value, refresh, delay)

        # Create a listener so the color values can be linked to this entity
        dispatcher.connect(
            self._value_added, ZWaveNetwork.SIGNAL_VALUE_ADDED)
        self._get_color_values()

    @property
    def dependent_value_ids(self):
        """List of value IDs a device depends on."""
        return [val.value_id for val in [
            self._value_color, self._value_color_channels] if val]

    def _get_color_values(self):
        """Search for color values available on this node."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        _LOGGER.debug("Searching for zwave color values")
        # Currently zwave nodes only exist with one color element per node.
        if self._value_color is None:
            for value_color in self._value.node.get_rgbbulbs().values():
                self._value_color = value_color

        if self._value_color_channels is None:
            self._value_color_channels = self.get_value(
                class_id=zwave.const.COMMAND_CLASS_SWITCH_COLOR,
                genre=zwave.const.GENRE_SYSTEM, type=zwave.const.TYPE_INT)

        if self._value_color and self._value_color_channels:
            _LOGGER.debug("Zwave node color values found.")
            dispatcher.disconnect(
                self._value_added, ZWaveNetwork.SIGNAL_VALUE_ADDED)
            self.update_properties()

    def _value_added(self, value):
        """Called when a value has been added to the network."""
        if self._value.node != value.node:
            return
        # Check for the missing color values
        self._get_color_values()

    def update_properties(self):
        """Update internal properties based on zwave values."""
        super().update_properties()

        if self._value_color is None:
            return
        if self._value_color_channels is None:
            return

        # Color Channels
        self._color_channels = self._value_color_channels.data

        # Color Data String
        data = self._value_color.data

        # RGB is always present in the openzwave color data string.
        self._rgb = [
            int(data[1:3], 16),
            int(data[3:5], 16),
            int(data[5:7], 16)]

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
                self._rgb = ct_to_rgb(self._ct)
            elif cold_white > 0:
                self._ct = TEMP_COLD_HASS
                self._rgb = ct_to_rgb(self._ct)
            else:
                # RGB color is being used. Just report midpoint.
                self._ct = TEMP_MID_HASS

        elif self._color_channels & COLOR_CHANNEL_WARM_WHITE:
            self._rgb = list(color_rgbw_to_rgb(*self._rgb, w=warm_white))

        elif self._color_channels & COLOR_CHANNEL_COLD_WHITE:
            self._rgb = list(color_rgbw_to_rgb(*self._rgb, w=cold_white))

        # If no rgb channels supported, report None.
        if not (self._color_channels & COLOR_CHANNEL_RED or
                self._color_channels & COLOR_CHANNEL_GREEN or
                self._color_channels & COLOR_CHANNEL_BLUE):
            self._rgb = None

    @property
    def rgb_color(self):
        """Return the rgb color."""
        return self._rgb

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self._ct

    def turn_on(self, **kwargs):
        """Turn the device on."""
        rgbw = None

        if ATTR_COLOR_TEMP in kwargs:
            # Color temperature. With the AEOTEC ZW098 bulb, only two color
            # temperatures are supported. The warm and cold channel values
            # indicate brightness for warm/cold color temperature.
            if self._zw098:
                if kwargs[ATTR_COLOR_TEMP] > TEMP_MID_HASS:
                    self._ct = TEMP_WARM_HASS
                    rgbw = b'#000000FF00'
                else:
                    self._ct = TEMP_COLD_HASS
                    rgbw = b'#00000000FF'

        elif ATTR_RGB_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGB_COLOR]
            if (not self._zw098 and (
                    self._color_channels & COLOR_CHANNEL_WARM_WHITE or
                    self._color_channels & COLOR_CHANNEL_COLD_WHITE)):
                rgbw = b'#'
                for colorval in color_rgb_to_rgbw(*self._rgb):
                    rgbw += format(colorval, '02x').encode('utf-8')
                rgbw += b'00'
            else:
                rgbw = b'#'
                for colorval in self._rgb:
                    rgbw += format(colorval, '02x').encode('utf-8')
                rgbw += b'0000'

        if rgbw and self._value_color:
            self._value_color.node.set_rgbw(self._value_color.value_id, rgbw)

        super().turn_on(**kwargs)

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._zw098:
            return SUPPORT_ZWAVE_COLORTEMP
        else:
            return SUPPORT_ZWAVE_COLOR
