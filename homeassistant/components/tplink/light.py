"""Support for TPLink lights."""
from __future__ import annotations

from collections.abc import Sequence
import logging
from typing import Any, Final, cast

from kasa import SmartBulb, SmartLightStrip
import voluptuous as vol

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import legacy_device_id
from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, async_refresh_after

_LOGGER = logging.getLogger(__name__)

SERVICE_RANDOM_EFFECT = "random_effect"
SERVICE_SEQUENCE_EFFECT = "sequence_effect"

HUE = vol.Range(min=0, max=360)
SAT = vol.Range(min=0, max=100)
VAL = vol.Range(min=0, max=100)
TRANSITION = vol.Range(min=0, max=6000)
HSV_SEQUENCE = vol.ExactSequence((HUE, SAT, VAL))

BASE_EFFECT_DICT: Final = {
    vol.Optional("brightness", default=100): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100)
    ),
    vol.Optional("duration", default=0): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=5000)
    ),
    vol.Optional("transition", default=0): vol.All(vol.Coerce(int), TRANSITION),
    vol.Optional("segments", default=[0]): vol.All(
        cv.ensure_list_csv,
        vol.Length(min=1, max=80),
        [vol.All(vol.Coerce(int), vol.Range(min=0, max=80))],
    ),
}

SEQUENCE_EFFECT_DICT: Final = {
    **BASE_EFFECT_DICT,
    vol.Required("sequence"): vol.All(
        cv.ensure_list,
        vol.Length(min=1, max=16),
        [vol.All(vol.Coerce(tuple), HSV_SEQUENCE)],
    ),
    vol.Optional("repeat_times", default=0): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=10)
    ),
    vol.Optional("spread", default=1): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=16)
    ),
    vol.Optional("direction", default=4): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=4)
    ),
}

RANDOM_EFFECT_DICT: Final = {
    **BASE_EFFECT_DICT,
    vol.Optional("fadeoff", default=0): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=3000)
    ),
    vol.Optional("hue_range"): vol.All(
        cv.ensure_list_csv, [vol.Coerce(int)], vol.ExactSequence((HUE, HUE))
    ),
    vol.Optional("saturation_range"): vol.All(
        cv.ensure_list_csv, [vol.Coerce(int)], vol.ExactSequence((SAT, SAT))
    ),
    vol.Optional("brightness_range"): vol.All(
        cv.ensure_list_csv, [vol.Coerce(int)], vol.ExactSequence((VAL, VAL))
    ),
    vol.Optional("transition_range"): vol.All(
        cv.ensure_list_csv,
        [vol.Coerce(int)],
        vol.ExactSequence((TRANSITION, TRANSITION)),
    ),
    vol.Required("init_states"): vol.All(
        cv.ensure_list_csv, [vol.Coerce(int)], HSV_SEQUENCE
    ),
    vol.Optional("random_seed", default=100): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=600)
    ),
    vol.Optional("backgrounds"): vol.All(
        cv.ensure_list,
        vol.Length(min=1, max=16),
        [vol.All(vol.Coerce(tuple), HSV_SEQUENCE)],
    ),
}


@callback
def _async_build_base_effect(
    brightness: int,
    duration: int,
    transition: int,
    segments: list[int],
) -> dict[str, Any]:
    return {
        "custom": 1,
        "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
        "brightness": brightness,
        "name": "Custom",
        "segments": segments,
        "expansion_strategy": 1,
        "enable": 1,
        "duration": duration,
        "transition": transition,
    }


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator: TPLinkDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    if coordinator.device.is_light_strip:
        async_add_entities(
            [
                TPLinkSmartLightStrip(
                    cast(SmartLightStrip, coordinator.device), coordinator
                )
            ]
        )
        platform = entity_platform.async_get_current_platform()
        platform.async_register_entity_service(
            SERVICE_RANDOM_EFFECT,
            RANDOM_EFFECT_DICT,
            "async_set_random_effect",
        )
        platform.async_register_entity_service(
            SERVICE_SEQUENCE_EFFECT,
            SEQUENCE_EFFECT_DICT,
            "async_set_sequence_effect",
        )
    elif coordinator.device.is_bulb or coordinator.device.is_dimmer:
        async_add_entities(
            [TPLinkSmartBulb(cast(SmartBulb, coordinator.device), coordinator)]
        )


class TPLinkSmartBulb(CoordinatedTPLinkEntity, LightEntity):
    """Representation of a TPLink Smart Bulb."""

    _attr_supported_features = LightEntityFeature.TRANSITION

    device: SmartBulb

    def __init__(
        self,
        device: SmartBulb,
        coordinator: TPLinkDataUpdateCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator)
        # For backwards compat with pyHS100
        if device.is_dimmer:
            # Dimmers used to use the switch format since
            # pyHS100 treated them as SmartPlug but the old code
            # created them as lights
            # https://github.com/home-assistant/core/blob/2021.9.7/homeassistant/components/tplink/common.py#L86
            self._attr_unique_id = legacy_device_id(device)
        else:
            self._attr_unique_id = device.mac.replace(":", "").upper()

    @callback
    def _async_extract_brightness_transition(
        self, **kwargs: Any
    ) -> tuple[int | None, int | None]:
        if (transition := kwargs.get(ATTR_TRANSITION)) is not None:
            transition = int(transition * 1_000)

        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            brightness = round((brightness * 100.0) / 255.0)

        if self.device.is_dimmer and transition is None:
            # This is a stopgap solution for inconsistent set_brightness handling
            # in the upstream library, see #57265.
            # This should be removed when the upstream has fixed the issue.
            # The device logic is to change the settings without turning it on
            # except when transition is defined, so we leverage that here for now.
            transition = 1

        return brightness, transition

    async def _async_set_hsv(
        self, hs_color: tuple[int, int], brightness: int | None, transition: int | None
    ) -> None:
        # TP-Link requires integers.
        hue, sat = tuple(int(val) for val in hs_color)
        await self.device.set_hsv(hue, sat, brightness, transition=transition)

    async def _async_turn_on_with_brightness(
        self, brightness: int | None, transition: int | None
    ) -> None:
        # Fallback to adjusting brightness or turning the bulb on
        if brightness is not None:
            await self.device.set_brightness(brightness, transition=transition)
            return
        await self.device.turn_on(transition=transition)

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness, transition = self._async_extract_brightness_transition(**kwargs)
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            await self.device.set_color_temp(
                int(kwargs[ATTR_COLOR_TEMP_KELVIN]),
                brightness=brightness,
                transition=transition,
            )
        if ATTR_HS_COLOR in kwargs:
            await self._async_set_hsv(kwargs[ATTR_HS_COLOR], brightness, transition)
        else:
            await self._async_turn_on_with_brightness(brightness, transition)

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if (transition := kwargs.get(ATTR_TRANSITION)) is not None:
            transition = int(transition * 1_000)
        await self.device.turn_off(transition=transition)

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return minimum supported color temperature."""
        return cast(int, self.device.valid_temperature_range.min)

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return maximum supported color temperature."""
        return cast(int, self.device.valid_temperature_range.max)

    @property
    def color_temp_kelvin(self) -> int:
        """Return the color temperature of this light."""
        return cast(int, self.device.color_temp)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return round((cast(int, self.device.brightness) * 255.0) / 100.0)

    @property
    def hs_color(self) -> tuple[int, int] | None:
        """Return the color."""
        hue, saturation, _ = self.device.hsv
        return hue, saturation

    @property
    def supported_color_modes(self) -> set[ColorMode | str] | None:
        """Return list of available color modes."""
        modes: set[ColorMode | str] = set()
        if self.device.is_variable_color_temp:
            modes.add(ColorMode.COLOR_TEMP)
        if self.device.is_color:
            modes.add(ColorMode.HS)
        if self.device.is_dimmable:
            modes.add(ColorMode.BRIGHTNESS)

        if not modes:
            modes.add(ColorMode.ONOFF)

        return modes

    @property
    def color_mode(self) -> ColorMode:
        """Return the active color mode."""
        if self.device.is_color:
            if self.device.is_variable_color_temp and self.device.color_temp:
                return ColorMode.COLOR_TEMP
            return ColorMode.HS
        if self.device.is_variable_color_temp:
            return ColorMode.COLOR_TEMP

        return ColorMode.BRIGHTNESS


class TPLinkSmartLightStrip(TPLinkSmartBulb):
    """Representation of a TPLink Smart Light Strip."""

    device: SmartLightStrip

    @property
    def supported_features(self) -> LightEntityFeature:
        """Flag supported features."""
        return super().supported_features | LightEntityFeature.EFFECT

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of available effects."""
        if effect_list := self.device.effect_list:
            return cast(list[str], effect_list)
        return None

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if (effect := self.device.effect) and effect["enable"]:
            return cast(str, effect["name"])
        return None

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness, transition = self._async_extract_brightness_transition(**kwargs)
        if ATTR_EFFECT in kwargs:
            await self.device.set_effect(
                kwargs[ATTR_EFFECT], brightness=brightness, transition=transition
            )
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            if self.effect:
                # If there is an effect in progress
                # we have to set an HSV value to clear the effect
                # before we can set a color temp
                await self.device.set_hsv(0, 0, brightness)
            await self.device.set_color_temp(
                int(kwargs[ATTR_COLOR_TEMP_KELVIN]),
                brightness=brightness,
                transition=transition,
            )
        elif ATTR_HS_COLOR in kwargs:
            await self._async_set_hsv(kwargs[ATTR_HS_COLOR], brightness, transition)
        else:
            await self._async_turn_on_with_brightness(brightness, transition)

    async def async_set_random_effect(
        self,
        brightness: int,
        duration: int,
        transition: int,
        segments: list[int],
        fadeoff: int,
        init_states: tuple[int, int, int],
        random_seed: int,
        backgrounds: Sequence[tuple[int, int, int]] | None = None,
        hue_range: tuple[int, int] | None = None,
        saturation_range: tuple[int, int] | None = None,
        brightness_range: tuple[int, int] | None = None,
        transition_range: tuple[int, int] | None = None,
    ) -> None:
        """Set a random effect."""
        effect: dict[str, Any] = {
            **_async_build_base_effect(brightness, duration, transition, segments),
            "type": "random",
            "init_states": [init_states],
            "random_seed": random_seed,
        }
        if backgrounds:
            effect["backgrounds"] = backgrounds
        if fadeoff:
            effect["fadeoff"] = fadeoff
        if hue_range:
            effect["hue_range"] = hue_range
        if saturation_range:
            effect["saturation_range"] = saturation_range
        if brightness_range:
            effect["brightness_range"] = brightness_range
            effect["brightness"] = min(
                brightness_range[1], max(brightness, brightness_range[0])
            )
        if transition_range:
            effect["transition_range"] = transition_range
            effect["transition"] = 0
        await self.device.set_custom_effect(effect)

    async def async_set_sequence_effect(
        self,
        brightness: int,
        duration: int,
        transition: int,
        segments: list[int],
        sequence: Sequence[tuple[int, int, int]],
        repeat_times: int,
        spread: int,
        direction: int,
    ) -> None:
        """Set a sequence effect."""
        effect: dict[str, Any] = {
            **_async_build_base_effect(brightness, duration, transition, segments),
            "type": "sequence",
            "sequence": sequence,
            "repeat_times": repeat_times,
            "spread": spread,
            "direction": direction,
        }
        await self.device.set_custom_effect(effect)
