"""Support for Homekit lights."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit lightbulb."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service):
        if service.short_type != ServicesTypes.LIGHTBULB:
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        async_add_entities([HomeKitLight(conn, info)], True)
        return True

    conn.add_listener(async_add_service)


class HomeKitLight(HomeKitEntity, LightEntity):
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
        features = 0

        if self.service.has(CharacteristicsTypes.BRIGHTNESS):
            features |= SUPPORT_BRIGHTNESS

        if self.service.has(CharacteristicsTypes.COLOR_TEMPERATURE):
            features |= SUPPORT_COLOR_TEMP

        if self.service.has(CharacteristicsTypes.HUE):
            features |= SUPPORT_COLOR

        if self.service.has(CharacteristicsTypes.SATURATION):
            features |= SUPPORT_COLOR

        return features

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
