"""
Support for Homekit lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.homekit_controller/
"""
import logging

from homeassistant.components.homekit_controller import (
    HomeKitEntity, KNOWN_ACCESSORIES)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, ATTR_COLOR_TEMP, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, SUPPORT_COLOR_TEMP, Light)

DEPENDENCIES = ['homekit_controller']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Homekit lighting."""
    if discovery_info is not None:
        accessory = hass.data[KNOWN_ACCESSORIES][discovery_info['serial']]
        add_entities([HomeKitLight(accessory, discovery_info)], True)


class HomeKitLight(HomeKitEntity, Light):
    """Representation of a Homekit light."""

    def __init__(self, *args):
        """Initialise the light."""
        super().__init__(*args)
        self._on = None
        self._brightness = None
        self._color_temperature = None
        self._hue = None
        self._saturation = None

    def update_characteristics(self, characteristics):
        """Synchronise light state with Home Assistant."""
        import homekit  # pylint: disable=import-error

        for characteristic in characteristics:
            ctype = characteristic['type']
            ctype = homekit.CharacteristicsTypes.get_short(ctype)
            if ctype == "on":
                self._chars['on'] = characteristic['iid']
                self._on = characteristic['value']
            elif ctype == 'brightness':
                self._chars['brightness'] = characteristic['iid']
                self._features |= SUPPORT_BRIGHTNESS
                self._brightness = characteristic['value']
            elif ctype == 'color-temperature':
                self._chars['color_temperature'] = characteristic['iid']
                self._features |= SUPPORT_COLOR_TEMP
                self._color_temperature = characteristic['value']
            elif ctype == "hue":
                self._chars['hue'] = characteristic['iid']
                self._features |= SUPPORT_COLOR
                self._hue = characteristic['value']
            elif ctype == "saturation":
                self._chars['saturation'] = characteristic['iid']
                self._features |= SUPPORT_COLOR
                self._saturation = characteristic['value']

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._on

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self._features & SUPPORT_BRIGHTNESS:
            return self._brightness * 255 / 100
        return None

    @property
    def hs_color(self):
        """Return the color property."""
        if self._features & SUPPORT_COLOR:
            return (self._hue, self._saturation)
        return None

    @property
    def color_temp(self):
        """Return the color temperature."""
        if self._features & SUPPORT_COLOR_TEMP:
            return self._color_temperature
        return None

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    def turn_on(self, **kwargs):
        """Turn the specified light on."""
        hs_color = kwargs.get(ATTR_HS_COLOR)
        temperature = kwargs.get(ATTR_COLOR_TEMP)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        characteristics = []
        if hs_color is not None:
            characteristics.append({'aid': self._aid,
                                    'iid': self._chars['hue'],
                                    'value': hs_color[0]})
            characteristics.append({'aid': self._aid,
                                    'iid': self._chars['saturation'],
                                    'value': hs_color[1]})
        if brightness is not None:
            characteristics.append({'aid': self._aid,
                                    'iid': self._chars['brightness'],
                                    'value': int(brightness * 100 / 255)})

        if temperature is not None:
            characteristics.append({'aid': self._aid,
                                    'iid': self._chars['color-temperature'],
                                    'value': int(temperature)})
        characteristics.append({'aid': self._aid,
                                'iid': self._chars['on'],
                                'value': True})
        self.put_characteristics(characteristics)

    def turn_off(self, **kwargs):
        """Turn the specified light off."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['on'],
                            'value': False}]
        self.put_characteristics(characteristics)
