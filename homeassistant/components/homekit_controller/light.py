"""Support for Homekit lights."""
import logging

from homekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    Light,
)
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit lightbulb."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        if service["stype"] != "lightbulb":
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([HomeKitLight(conn, info)], True)
        return True

    conn.add_listener(async_add_service)


class HomeKitLight(HomeKitEntity, Light):
    """Representation of a Homekit light."""

    def __init__(self, *args):
        """Initialise the light."""
        super().__init__(*args)
        self._on = False
        self._brightness = 0
        self._color_temperature = 0
        self._hue = 0
        self._saturation = 0

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ON,
            CharacteristicsTypes.BRIGHTNESS,
            CharacteristicsTypes.COLOR_TEMPERATURE,
            CharacteristicsTypes.HUE,
            CharacteristicsTypes.SATURATION,
        ]

    def _setup_brightness(self, char):
        self._features |= SUPPORT_BRIGHTNESS

    def _setup_color_temperature(self, char):
        self._features |= SUPPORT_COLOR_TEMP

    def _setup_hue(self, char):
        self._features |= SUPPORT_COLOR

    def _setup_saturation(self, char):
        self._features |= SUPPORT_COLOR

    def _update_on(self, value):
        self._on = value

    def _update_brightness(self, value):
        self._brightness = value

    def _update_color_temperature(self, value):
        self._color_temperature = value

    def _update_hue(self, value):
        self._hue = value

    def _update_saturation(self, value):
        self._saturation = value

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._on

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness * 255 / 100

    @property
    def hs_color(self):
        """Return the color property."""
        return (self._hue, self._saturation)

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self._color_temperature

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    async def async_turn_on(self, **kwargs):
        """Turn the specified light on."""
        hs_color = kwargs.get(ATTR_HS_COLOR)
        temperature = kwargs.get(ATTR_COLOR_TEMP)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        characteristics = []
        if hs_color is not None:
            characteristics.append(
                {"aid": self._aid, "iid": self._chars["hue"], "value": hs_color[0]}
            )
            characteristics.append(
                {
                    "aid": self._aid,
                    "iid": self._chars["saturation"],
                    "value": hs_color[1],
                }
            )
        if brightness is not None:
            characteristics.append(
                {
                    "aid": self._aid,
                    "iid": self._chars["brightness"],
                    "value": int(brightness * 100 / 255),
                }
            )

        if temperature is not None:
            characteristics.append(
                {
                    "aid": self._aid,
                    "iid": self._chars["color-temperature"],
                    "value": int(temperature),
                }
            )
        characteristics.append(
            {"aid": self._aid, "iid": self._chars["on"], "value": True}
        )
        await self._accessory.put_characteristics(characteristics)

    async def async_turn_off(self, **kwargs):
        """Turn the specified light off."""
        characteristics = [{"aid": self._aid, "iid": self._chars["on"], "value": False}]
        await self._accessory.put_characteristics(characteristics)
