"""Support for Aqualink pool lights."""
from iaqualink import AqualinkLightEffect

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    DOMAIN,
    SUPPORT_BRIGHTNESS,
    SUPPORT_EFFECT,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import AqualinkEntity, refresh_system
from .const import DOMAIN as AQUALINK_DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up discovered lights."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkLight(dev))
    async_add_entities(devs, True)


class HassAqualinkLight(AqualinkEntity, LightEntity):
    """Representation of a light."""

    @property
    def name(self) -> str:
        """Return the name of the light."""
        return self.dev.label

    @property
    def is_on(self) -> bool:
        """Return whether the light is on or off."""
        return self.dev.is_on

    @refresh_system
    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the light.

        This handles brightness and light effects for lights that do support
        them.
        """
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)

        # For now I'm assuming lights support either effects or brightness.
        if effect:
            effect = AqualinkLightEffect[effect].value
            await self.dev.set_effect(effect)
        elif brightness:
            # Aqualink supports percentages in 25% increments.
            pct = int(round(brightness * 4.0 / 255)) * 25
            await self.dev.set_brightness(pct)
        else:
            await self.dev.turn_on()

    @refresh_system
    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the light."""
        await self.dev.turn_off()

    @property
    def brightness(self) -> int:
        """Return current brightness of the light.

        The scale needs converting between 0-100 and 0-255.
        """
        return self.dev.brightness * 255 / 100

    @property
    def effect(self) -> str:
        """Return the current light effect if supported."""
        return AqualinkLightEffect(self.dev.effect).name

    @property
    def effect_list(self) -> list:
        """Return supported light effects."""
        return list(AqualinkLightEffect.__members__)

    @property
    def supported_features(self) -> int:
        """Return the list of features supported by the light."""
        if self.dev.is_dimmer:
            return SUPPORT_BRIGHTNESS

        if self.dev.is_color:
            return SUPPORT_EFFECT

        return 0
