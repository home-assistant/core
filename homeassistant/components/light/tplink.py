"""
Support for TPLink lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.tplink/
"""
import logging
from homeassistant.const import (CONF_HOST, CONF_NAME)
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_KELVIN,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP)
from homeassistant.util.color import \
    color_temperature_mired_to_kelvin as mired_to_kelvin
from homeassistant.util.color import \
    color_temperature_kelvin_to_mired as kelvin_to_mired

REQUIREMENTS = ['pyHS100==0.2.4.2']

_LOGGER = logging.getLogger(__name__)

SUPPORT_TPLINK = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Initialise pyLB100 SmartBulb."""
    from pyHS100 import SmartBulb
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    add_devices([TPLinkSmartBulb(SmartBulb(host), name)], True)


def brightness_to_percentage(byt):
    """Convert brightness from absolute 0..255 to percentage."""
    return (byt*100.0)/255.0


def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return (percent*255.0)/100.0


class TPLinkSmartBulb(Light):
    """Representation of a TPLink Smart Bulb."""

    def __init__(self, smartbulb, name):
        """Initialize the bulb."""
        self.smartbulb = smartbulb

        # Use the name set on the device if not set
        if name is None:
            self._name = self.smartbulb.alias
        else:
            self._name = name

        self._state = None
        _LOGGER.debug("Setting up TP-Link Smart Bulb")

    @property
    def name(self):
        """Return the name of the Smart Bulb, if any."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_COLOR_TEMP in kwargs:
            self.smartbulb.color_temp = \
                mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])
        if ATTR_KELVIN in kwargs:
            self.smartbulb.color_temp = kwargs[ATTR_KELVIN]
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
            self.smartbulb.brightness = brightness_to_percentage(brightness)

        self.smartbulb.state = self.smartbulb.BULB_STATE_ON

    def turn_off(self):
        """Turn the light off."""
        self.smartbulb.state = self.smartbulb.BULB_STATE_OFF

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds for HA."""
        if self.smartbulb.is_color:
            if (self.smartbulb.color_temp is not None and
                    self.smartbulb.color_temp != 0):
                return kelvin_to_mired(self.smartbulb.color_temp)
            else:
                return None
        else:
            return None

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return brightness_from_percentage(self.smartbulb.brightness)

    @property
    def is_on(self):
        """True if device is on."""
        return self.smartbulb.state == \
            self.smartbulb.BULB_STATE_ON

    def update(self):
        """Update the TP-Link Bulb's state."""
        from pyHS100 import SmartPlugException
        try:
            self._state = self.smartbulb.state == \
                self.smartbulb.BULB_STATE_ON

        except (SmartPlugException, OSError) as ex:
            _LOGGER.warning('Could not read state for %s: %s', self.name, ex)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_TPLINK
