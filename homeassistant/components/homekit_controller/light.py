"""Support for Homekit lights."""
import logging

from aiohomekit.model.characteristics import CharacteristicsTypes

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

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.service.value(CharacteristicsTypes.ON)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.service.value(CharacteristicsTypes.BRIGHTNESS) * 255 / 100

    @property
    def hs_color(self):
        """Return the color property."""
        return (
            self.service.value(CharacteristicsTypes.HUE),
            self.service.value(CharacteristicsTypes.SATURATION),
        )

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self.service.value(CharacteristicsTypes.COLOR_TEMPERATURE)

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    async def async_turn_on(self, **kwargs):
        """Turn the specified light on."""
        hs_color = kwargs.get(ATTR_HS_COLOR)
        temperature = kwargs.get(ATTR_COLOR_TEMP)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        characteristics = {}

        if hs_color is not None:
            characteristics.update(
                {
                    CharacteristicsTypes.HUE: hs_color[0],
                    CharacteristicsTypes.SATURATION: hs_color[1],
                }
            )

        if brightness is not None:
            characteristics[CharacteristicsTypes.BRIGHTNESS] = int(
                brightness * 100 / 255
            )

        if temperature is not None:
            characteristics[CharacteristicsTypes.COLOR_TEMPERATURE] = int(temperature)

        characteristics[CharacteristicsTypes.ON] = True

        await self.async_put_characteristics(characteristics)

    async def async_turn_off(self, **kwargs):
        """Turn the specified light off."""
        await self.async_put_characteristics({CharacteristicsTypes.ON: False})
