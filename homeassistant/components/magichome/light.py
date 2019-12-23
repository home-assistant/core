"""Support for the MagicHome lights."""
from homeassistant.components.light import (ATTR_BRIGHTNESS, ATTR_COLOR_TEMP,
                                            ATTR_HS_COLOR, ENTITY_ID_FORMAT,
                                            SUPPORT_BRIGHTNESS, SUPPORT_COLOR,
                                            SUPPORT_COLOR_TEMP, Light)
from homeassistant.util import color as colorutil

from . import DATA_MAGICHOME, MagicHomeDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up MagicHome light platform."""
    if discovery_info is None:
        return
    magichome = hass.data[DATA_MAGICHOME]
    dev_ids = discovery_info.get("dev_ids")
    devices = []
    for dev_id in dev_ids:
        device = magichome.get_device_by_id(dev_id)
        if device is None:
            continue
        devices.append(MagicHomeLight(device))
    add_entities(devices)


class MagicHomeLight(MagicHomeDevice, Light):
    """MagicHome light device."""

    def __init__(self, magichome):
        """Init MagicHome light device."""
        super().__init__(magichome)
        self.entity_id = ENTITY_ID_FORMAT.format(magichome.object_id())

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return int(self.magichome.brightness())

    @property
    def hs_color(self):
        """Return the hs_color of the light."""
        return tuple(map(int, self.magichome.hs_color()))

    @property
    def color_temp(self):
        """Return the color_temp of the light."""
        if self.magichome.color_temp() is None:
            return None
        color_temp = int(self.magichome.color_temp())
        return colorutil.color_temperature_kelvin_to_mired(color_temp)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.magichome.state()

    @property
    def min_mireds(self):
        """Return color temperature min mireds."""
        return colorutil.color_temperature_kelvin_to_mired(
            self.magichome.min_color_temp()
        )

    @property
    def max_mireds(self):
        """Return color temperature max mireds."""
        return colorutil.color_temperature_kelvin_to_mired(
            self.magichome.max_color_temp()
        )

    def turn_on(self, **kwargs):
        """Turn on or control the light."""
        if (
            ATTR_BRIGHTNESS not in kwargs
            and ATTR_HS_COLOR not in kwargs
            and ATTR_COLOR_TEMP not in kwargs
        ):
            self.magichome.turn_on()
        if ATTR_BRIGHTNESS in kwargs:
            self.magichome.set_brightness(kwargs[ATTR_BRIGHTNESS])
        if ATTR_HS_COLOR in kwargs:
            self.magichome.set_color(kwargs[ATTR_HS_COLOR])
        if ATTR_COLOR_TEMP in kwargs:
            color_temp = colorutil.color_temperature_mired_to_kelvin(
                kwargs[ATTR_COLOR_TEMP]
            )
            self.magichome.set_color_temp(color_temp)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self.magichome.turn_off()

    @property
    def supported_features(self):
        """Flag supported features."""
        supports = SUPPORT_BRIGHTNESS
        if self.magichome.support_color():
            supports = supports | SUPPORT_COLOR
        if self.magichome.support_color_temp():
            supports = supports | SUPPORT_COLOR_TEMP
        return supports
