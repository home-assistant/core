"""Support for Hue lights."""
from __future__ import annotations

from typing import Any

from aiohue import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.lights import LightsController
from aiohue.v2.models.feature import EffectStatus, TimedEffectStatus
from aiohue.v2.models.light import Light

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    FLASH_SHORT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..bridge import HueBridge
from ..const import DOMAIN
from .entity import HueBaseEntity
from .helpers import (
    normalize_hue_brightness,
    normalize_hue_colortemp,
    normalize_hue_transition,
)

EFFECT_NONE = "None"
FALLBACK_MIN_MIREDS = 153  # 6500 K
FALLBACK_MAX_MIREDS = 500  # 2000 K
FALLBACK_MIREDS = 173  # halfway


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hue Light from Config Entry."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: HueBridgeV2 = bridge.api
    controller: LightsController = api.lights

    @callback
    def async_add_light(event_type: EventType, resource: Light) -> None:
        """Add Hue Light."""
        light = HueLight(bridge, controller, resource)
        async_add_entities([light])

    # add all current items in controller
    for light in controller:
        async_add_light(EventType.RESOURCE_ADDED, resource=light)

    # register listener for new lights
    config_entry.async_on_unload(
        controller.subscribe(async_add_light, event_filter=EventType.RESOURCE_ADDED)
    )


class HueLight(HueBaseEntity, LightEntity):
    """Representation of a Hue light."""

    def __init__(
        self, bridge: HueBridge, controller: LightsController, resource: Light
    ) -> None:
        """Initialize the light."""
        super().__init__(bridge, controller, resource)
        if self.resource.alert and self.resource.alert.action_values:
            self._attr_supported_features |= LightEntityFeature.FLASH
        self.resource = resource
        self.controller = controller
        self._supported_color_modes: set[ColorMode | str] = set()
        if self.resource.supports_color:
            self._supported_color_modes.add(ColorMode.XY)
        if self.resource.supports_color_temperature:
            self._supported_color_modes.add(ColorMode.COLOR_TEMP)
        if self.resource.supports_dimming:
            if len(self._supported_color_modes) == 0:
                # only add color mode brightness if no color variants
                self._supported_color_modes.add(ColorMode.BRIGHTNESS)
            # support transition if brightness control
            self._attr_supported_features |= LightEntityFeature.TRANSITION
        # get list of supported effects (combine effects and timed_effects)
        self._attr_effect_list = []
        if effects := resource.effects:
            self._attr_effect_list = [
                x.value for x in effects.status_values if x != EffectStatus.NO_EFFECT
            ]
        if timed_effects := resource.timed_effects:
            self._attr_effect_list += [
                x.value
                for x in timed_effects.status_values
                if x != TimedEffectStatus.NO_EFFECT
            ]
        if len(self._attr_effect_list) > 0:
            self._attr_effect_list.insert(0, EFFECT_NONE)
            self._attr_supported_features |= LightEntityFeature.EFFECT

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if dimming := self.resource.dimming:
            # Hue uses a range of [0, 100] to control brightness.
            return round((dimming.brightness / 100) * 255)
        return None

    @property
    def is_on(self) -> bool:
        """Return true if device is on (brightness above 0)."""
        return self.resource.on.on

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if color_temp := self.resource.color_temperature:
            # Hue lights return `mired_valid` to indicate CT is active
            if color_temp.mirek_valid and color_temp.mirek is not None:
                return ColorMode.COLOR_TEMP
        if self.resource.supports_color:
            return ColorMode.XY
        if self.resource.supports_dimming:
            return ColorMode.BRIGHTNESS
        # fallback to on_off
        return ColorMode.ONOFF

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color."""
        if color := self.resource.color:
            return (color.xy.x, color.xy.y)
        return None

    @property
    def color_temp(self) -> int:
        """Return the color temperature."""
        if color_temp := self.resource.color_temperature:
            return color_temp.mirek
        # return a fallback value to prevent issues with mired->kelvin conversions
        return FALLBACK_MIREDS

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        if color_temp := self.resource.color_temperature:
            return color_temp.mirek_schema.mirek_minimum
        # return a fallback value to prevent issues with mired->kelvin conversions
        return FALLBACK_MIN_MIREDS

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        if color_temp := self.resource.color_temperature:
            return color_temp.mirek_schema.mirek_maximum
        # return a fallback value to prevent issues with mired->kelvin conversions
        return FALLBACK_MAX_MIREDS

    @property
    def supported_color_modes(self) -> set | None:
        """Flag supported features."""
        return self._supported_color_modes

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the optional state attributes."""
        return {
            "mode": self.resource.mode.value,
            "dynamics": self.resource.dynamics.status.value,
        }

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if effects := self.resource.effects:
            if effects.status != EffectStatus.NO_EFFECT:
                return effects.status.value
        if timed_effects := self.resource.timed_effects:
            if timed_effects.status != TimedEffectStatus.NO_EFFECT:
                return timed_effects.status.value
        return EFFECT_NONE

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        transition = normalize_hue_transition(kwargs.get(ATTR_TRANSITION))
        xy_color = kwargs.get(ATTR_XY_COLOR)
        color_temp = normalize_hue_colortemp(kwargs.get(ATTR_COLOR_TEMP))
        brightness = normalize_hue_brightness(kwargs.get(ATTR_BRIGHTNESS))
        flash = kwargs.get(ATTR_FLASH)
        effect = effect_str = kwargs.get(ATTR_EFFECT)
        if effect_str in (EFFECT_NONE, EFFECT_NONE.lower()):
            effect = EffectStatus.NO_EFFECT
        elif effect_str is not None:
            # work out if we got a regular effect or timed effect
            effect = EffectStatus(effect_str)
            if effect == EffectStatus.UNKNOWN:
                effect = TimedEffectStatus(effect_str)
                if transition is None:
                    # a transition is required for timed effect, default to 10 minutes
                    transition = 600000

        if flash is not None:
            await self.async_set_flash(flash)
            # flash cannot be sent with other commands at the same time or result will be flaky
            # Hue's default behavior is that a light returns to its previous state for short
            # flash (identify) and the light is kept turned on for long flash (breathe effect)
            # Why is this flash alert/effect hidden in the turn_on/off commands ?
            return

        await self.bridge.async_request_call(
            self.controller.set_state,
            id=self.resource.id,
            on=True,
            brightness=brightness,
            color_xy=xy_color,
            color_temp=color_temp,
            transition_time=transition,
            effect=effect,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        transition = normalize_hue_transition(kwargs.get(ATTR_TRANSITION))
        flash = kwargs.get(ATTR_FLASH)

        if flash is not None:
            await self.async_set_flash(flash)
            # flash cannot be sent with other commands at the same time or result will be flaky
            # Hue's default behavior is that a light returns to its previous state for short
            # flash (identify) and the light is kept turned on for long flash (breathe effect)
            return

        await self.bridge.async_request_call(
            self.controller.set_state,
            id=self.resource.id,
            on=False,
            transition_time=transition,
        )

    async def async_set_flash(self, flash: str) -> None:
        """Send flash command to light."""
        await self.bridge.async_request_call(
            self.controller.set_flash,
            id=self.resource.id,
            short=flash == FLASH_SHORT,
        )
