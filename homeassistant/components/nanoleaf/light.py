"""Support for Nanoleaf Lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ESSENTIALS_MODEL_PREFIXES
from .coordinator import NanoleafConfigEntry, NanoleafCoordinator
from .entity import NanoleafEntity

RESERVED_EFFECTS = ("*Solid*", "*Static*", "*Dynamic*")
DEFAULT_NAME = "Nanoleaf"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanoleafConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nanoleaf light."""
    async_add_entities([NanoleafLight(entry.runtime_data)])


class NanoleafLight(NanoleafEntity, LightEntity):
    """Representation of a Nanoleaf Light."""

    _attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
    _attr_name = None
    _attr_translation_key = "light"

    def __init__(self, coordinator: NanoleafCoordinator) -> None:
        """Initialize the Nanoleaf light."""
        super().__init__(coordinator)
        self._attr_unique_id = self._nanoleaf.serial_no
        self._attr_max_color_temp_kelvin = self._nanoleaf.color_temperature_max
        self._attr_min_color_temp_kelvin = self._nanoleaf.color_temperature_min
        # All devices support effects (Panels via library, Essentials via direct HTTP)
        self._attr_supported_features = (
            LightEntityFeature.EFFECT | LightEntityFeature.TRANSITION
        )

    @property
    def _is_essentials(self) -> bool:
        """Return True if this is an Essentials device."""
        model = self._nanoleaf.model or ""
        return model.startswith(ESSENTIALS_MODEL_PREFIXES)

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return int(self._nanoleaf.brightness * 2.55)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature value in Kelvin."""
        return self._nanoleaf.color_temperature

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if self._is_essentials:
            # Essentials: use coordinator data fetched via direct HTTP
            effect = self.coordinator.essentials_current_effect
            if effect is None or effect in RESERVED_EFFECTS:
                return None
            return effect
        # Panels: use library data
        # The API returns the *Solid* effect if the Nanoleaf is in HS or CT mode.
        # The effects *Static* and *Dynamic* are not supported by Home Assistant.
        # These reserved effects are implicitly set and are not in the effect_list.
        # https://forum.nanoleaf.me/docs/openapi#_byoot0bams8f
        effect = getattr(self._nanoleaf, "effect", None)
        if effect is None or effect in RESERVED_EFFECTS:
            return None
        return effect

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        if self._is_essentials:
            # Essentials: use coordinator data fetched via direct HTTP
            return self.coordinator.essentials_effects_list
        # Panels: use library data
        return getattr(self._nanoleaf, "effects_list", None)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._nanoleaf.is_on

    @property
    def hs_color(self) -> tuple[int, int]:
        """Return the color in HS."""
        return self._nanoleaf.hue, self._nanoleaf.saturation

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the color mode of the light."""
        # According to API docs, color mode is "ct", "effect" or "hs"
        # https://forum.nanoleaf.me/docs/openapi#_4qgqrz96f44d
        if self._nanoleaf.color_mode == "ct":
            return ColorMode.COLOR_TEMP
        # Home Assistant does not have an "effect" color mode, just report hs
        return ColorMode.HS

    async def _set_essentials_effect(self, effect: str) -> None:
        """Set effect on Essentials device via direct HTTP."""
        session = async_get_clientsession(self.hass)
        token = self.coordinator.config_entry.data[CONF_TOKEN]
        base_url = (
            f"http://{self._nanoleaf.host}:{self._nanoleaf.port}/api/v1/{token}"
        )
        async with session.put(f"{base_url}/effects", json={"select": effect}):
            pass

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        effect = kwargs.get(ATTR_EFFECT)
        transition = kwargs.get(ATTR_TRANSITION)

        if effect:
            effect_list = self.effect_list
            if effect_list is None or effect not in effect_list:
                raise ValueError(
                    f"Attempting to apply effect not in the effect list: '{effect}'"
                )
            if self._is_essentials:
                await self._set_essentials_effect(effect)
            else:
                await self._nanoleaf.set_effect(effect)
        elif hs_color:
            hue, saturation = hs_color
            await self._nanoleaf.set_hue(int(hue))
            await self._nanoleaf.set_saturation(int(saturation))
        elif color_temp_kelvin:
            await self._nanoleaf.set_color_temperature(color_temp_kelvin)
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
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        transition: float | None = kwargs.get(ATTR_TRANSITION)
        await self._nanoleaf.turn_off(None if transition is None else int(transition))
        await self.coordinator.async_refresh()
