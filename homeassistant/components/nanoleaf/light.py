"""Support for Nanoleaf Lights."""
from __future__ import annotations

from aionanoleaf import Nanoleaf, Unavailable
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import color as color_util
from homeassistant.util.color import (
    color_temperature_mired_to_kelvin as mired_to_kelvin,
)

from .const import DOMAIN

RESERVED_EFFECTS = ("*Solid*", "*Static*", "*Dynamic*")
DEFAULT_NAME = "Nanoleaf"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import Nanoleaf light platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: config[CONF_HOST], CONF_TOKEN: config[CONF_TOKEN]},
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nanoleaf light."""
    nanoleaf: Nanoleaf = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NanoleafLight(nanoleaf)])


class NanoleafLight(LightEntity):
    """Representation of a Nanoleaf Light."""

    def __init__(self, nanoleaf: Nanoleaf) -> None:
        """Initialize an Nanoleaf light."""
        self._nanoleaf = nanoleaf
        self._attr_unique_id = self._nanoleaf.serial_no
        self._attr_name = self._nanoleaf.name
        self._attr_min_mireds = 154
        self._attr_max_mireds = 833

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return int(self._nanoleaf.brightness * 2.55)

    @property
    def color_temp(self):
        """Return the current color temperature."""
        return color_util.color_temperature_kelvin_to_mired(
            self._nanoleaf.color_temperature
        )

    @property
    def effect(self):
        """Return the current effect."""
        # The API returns the *Solid* effect if the Nanoleaf is in HS or CT mode.
        # The effects *Static* and *Dynamic* are not supported by Home Assistant.
        # These reserved effects are implicitly set and are not in the effect_list.
        # https://forum.nanoleaf.me/docs/openapi#_byoot0bams8f
        return (
            None if self._nanoleaf.effect in RESERVED_EFFECTS else self._nanoleaf.effect
        )

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._nanoleaf.effects_list

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:triangle-outline"

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._nanoleaf.is_on

    @property
    def hs_color(self):
        """Return the color in HS."""
        return self._nanoleaf.hue, self._nanoleaf.saturation

    @property
    def supported_features(self):
        """Flag supported features."""
        return (
            SUPPORT_BRIGHTNESS
            | SUPPORT_COLOR_TEMP
            | SUPPORT_EFFECT
            | SUPPORT_COLOR
            | SUPPORT_TRANSITION
        )

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        color_temp_mired = kwargs.get(ATTR_COLOR_TEMP)
        effect = kwargs.get(ATTR_EFFECT)
        transition = kwargs.get(ATTR_TRANSITION)

        if hs_color:
            hue, saturation = hs_color
            await self._nanoleaf.set_hue(int(hue))
            await self._nanoleaf.set_saturation(int(saturation))
        if color_temp_mired:
            await self._nanoleaf.set_color_temperature(
                mired_to_kelvin(color_temp_mired)
            )
        if transition:
            if brightness:  # tune to the required brightness in n seconds
                await self._nanoleaf.set_brightness(
                    int(brightness / 2.55), transition=int(kwargs[ATTR_TRANSITION])
                )
            else:  # If brightness is not specified, assume full brightness
                await self._nanoleaf.set_brightness(100, transition=int(transition))
        else:  # If no transition is occurring, turn on the light
            await self._nanoleaf.turn_on()
            if brightness:
                await self._nanoleaf.set_brightness(int(brightness / 2.55))
        if effect:
            if effect not in self.effect_list:
                raise ValueError(
                    f"Attempting to apply effect not in the effect list: '{effect}'"
                )
            await self._nanoleaf.set_effect(effect)

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        transition = kwargs.get(ATTR_TRANSITION)
        await self._nanoleaf.turn_off(transition)

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        try:
            await self._nanoleaf.get_info()
        except Unavailable:
            self._attr_available = False
            return
        self._attr_available = True
