"""Support for Hue lights."""

import asyncio
from typing import Any, override

from aiohue import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.lights import LightsController
from aiohue.v2.models.feature import EffectStatus, TimedEffectStatus
from aiohue.v2.models.light import Light

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    EFFECT_OFF,
    FLASH_SHORT,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
    filter_supported_color_modes,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.group import IntegrationSpecificGroup
from homeassistant.util import color as color_util

from ..bridge import HueBridge, HueConfigEntry
from .entity import HueBaseEntity
from .helpers import (
    hue_brightness_to_ha,
    normalize_hue_brightness,
    normalize_hue_colortemp,
    normalize_hue_transition,
)

FALLBACK_MIN_MIREDS = 153  # hue default for most lights
FALLBACK_MAX_MIREDS = 500  # hue default for most lights
FALLBACK_KELVIN = 5800  # halfway
GRADIENT_COALESCE_DELAY = 0.1  # seconds to collect concurrent segment writes


def gradient_segment_unique_id(resource: Light, number: int) -> str:
    """Return the unique id of a gradient segment entity."""
    return f"{resource.id}_segment_{number}"


def gradient_point_color(resource: Light, index: int) -> tuple[float, float]:
    """Return the color of a gradient point.

    Falls back to the color of the whole light, which is what the bridge
    reports while no gradient is active.
    """
    points = resource.gradient.points
    xy = points[index].color.xy if index < len(points) else resource.color.xy
    return (xy.x, xy.y)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hue Light from Config Entry."""
    bridge = config_entry.runtime_data
    api: HueBridgeV2 = bridge.api
    controller: LightsController = api.lights

    def make_light_entities(resource: Light) -> list[HueBaseEntity]:
        """Create the light entity plus a segment entity per gradient point."""
        entities: list[HueBaseEntity] = [HueLight(bridge, controller, resource)]
        if resource.gradient is not None:
            writer = HueGradientWriter(bridge, controller, resource)
            entities.extend(
                HueGradientSegmentLight(bridge, controller, resource, writer, number)
                for number in range(1, resource.gradient.points_capable + 1)
            )
        return entities

    @callback
    def async_add_light(event_type: EventType, resource: Light) -> None:
        """Add Hue Light."""
        async_add_entities(make_light_entities(resource))

    # add all current items in controller
    async_add_entities(
        entity for light in controller for entity in make_light_entities(light)
    )
    # register listener for new lights
    config_entry.async_on_unload(
        controller.subscribe(async_add_light, event_filter=EventType.RESOURCE_ADDED)
    )


# pylint: disable-next=home-assistant-enforce-class-module
class HueLight(HueBaseEntity, LightEntity):
    """Representation of a Hue light."""

    _fixed_color_mode: ColorMode | None = None
    entity_description = LightEntityDescription(
        key="hue_light", translation_key="hue_light", has_entity_name=True, name=None
    )

    def __init__(
        self, bridge: HueBridge, controller: LightsController, resource: Light
    ) -> None:
        """Initialize the light."""
        super().__init__(bridge, controller, resource)
        if self.resource.alert and self.resource.alert.action_values:
            self._attr_supported_features |= LightEntityFeature.FLASH
        self.resource = resource
        self.controller = controller
        supported_color_modes = {ColorMode.ONOFF}
        if self.resource.supports_color:
            supported_color_modes.add(ColorMode.XY)
        if self.resource.supports_color_temperature:
            supported_color_modes.add(ColorMode.COLOR_TEMP)
        if self.resource.supports_dimming:
            supported_color_modes.add(ColorMode.BRIGHTNESS)
            # support transition if brightness control
            self._attr_supported_features |= LightEntityFeature.TRANSITION
        supported_color_modes = filter_supported_color_modes(supported_color_modes)
        self._attr_supported_color_modes = supported_color_modes
        if len(self._attr_supported_color_modes) == 1:
            # If the light supports only a single color mode, set it now
            self._fixed_color_mode = next(iter(self._attr_supported_color_modes))
        self._last_brightness: float | None = None
        self._color_temp_active: bool = False
        # get list of supported effects (combine effects and timed_effects)
        self._attr_effect_list = []
        if effects := resource.effects:
            self._attr_effect_list = [
                x.value
                for x in effects.status_values
                if x not in (EffectStatus.NO_EFFECT, EffectStatus.UNKNOWN)
            ]
        if timed_effects := resource.timed_effects:
            self._attr_effect_list += [
                x.value
                for x in timed_effects.status_values
                if x != TimedEffectStatus.NO_EFFECT
            ]
        if len(self._attr_effect_list) > 0:
            self._attr_effect_list.insert(0, EFFECT_OFF)
            self._attr_supported_features |= LightEntityFeature.EFFECT
        if (gradient := resource.gradient) is not None:
            self.group = IntegrationSpecificGroup(
                self,
                [
                    gradient_segment_unique_id(resource, number)
                    for number in range(1, gradient.points_capable + 1)
                ],
            )

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if dimming := self.resource.dimming:
            return hue_brightness_to_ha(dimming.brightness)
        return None

    @property
    @override
    def is_on(self) -> bool:
        """Return true if device is on (brightness above 0)."""
        return self.resource.on.on

    @property
    @override
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._fixed_color_mode:
            # The light supports only a single color mode, return it
            return self._fixed_color_mode

        # The light supports both color temperature and XY, determine which
        # mode the light is in
        if self.color_temp_active:
            return ColorMode.COLOR_TEMP
        return ColorMode.XY

    @property
    def color_temp_active(self) -> bool:
        """Return if the light is in Color Temperature mode."""
        color_temp = self.resource.color_temperature
        # a zero mirek is not a valid color temperature either
        if color_temp is None or not color_temp.mirek:
            return False
        # Official Hue lights return `mirek_valid` to indicate CT is active
        # while non-official lights do not.
        if self.device.product_data.certified:
            return self.resource.color_temperature.mirek_valid
        return self._color_temp_active

    @property
    @override
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color."""
        if color := self.resource.color:
            return (color.xy.x, color.xy.y)
        return None

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature value in Kelvin."""
        if (color_temp := self.resource.color_temperature) and color_temp.mirek:
            return color_util.color_temperature_mired_to_kelvin(color_temp.mirek)
        # return a fallback value to prevent issues with mired->kelvin conversions
        return FALLBACK_KELVIN

    @property
    def max_color_temp_mireds(self) -> int:
        """Return the warmest color_temp in mireds that this light supports."""
        if (color_temp := self.resource.color_temperature) and (
            mirek_max := color_temp.mirek_schema.mirek_maximum
        ):
            return mirek_max
        # return a fallback value if the light doesn't provide valid limits
        return FALLBACK_MAX_MIREDS

    @property
    def min_color_temp_mireds(self) -> int:
        """Return the coldest color_temp in mireds that this light supports."""
        if (color_temp := self.resource.color_temperature) and (
            mirek_min := color_temp.mirek_schema.mirek_minimum
        ):
            return mirek_min
        # return a fallback value if the light doesn't provide valid limits
        return FALLBACK_MIN_MIREDS

    @property
    @override
    def max_color_temp_kelvin(self) -> int:
        """Return the coldest color_temp_kelvin that this light supports."""
        return color_util.color_temperature_mired_to_kelvin(self.min_color_temp_mireds)

    @property
    @override
    def min_color_temp_kelvin(self) -> int:
        """Return the warmest color_temp_kelvin that this light supports."""
        return color_util.color_temperature_mired_to_kelvin(self.max_color_temp_mireds)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the optional state attributes."""
        return {
            "mode": self.resource.mode.value,
            "dynamics": self.resource.dynamics.status.value,
        }

    @property
    @override
    def effect(self) -> str | None:
        """Return the current effect."""
        if effects := self.resource.effects:
            if effects.status != EffectStatus.NO_EFFECT:
                return effects.status.value
        if timed_effects := self.resource.timed_effects:
            if timed_effects.status != TimedEffectStatus.NO_EFFECT:
                return timed_effects.status.value
        return EFFECT_OFF

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        transition = normalize_hue_transition(kwargs.get(ATTR_TRANSITION))
        xy_color = kwargs.get(ATTR_XY_COLOR)
        color_temp = normalize_hue_colortemp(
            kwargs.get(ATTR_COLOR_TEMP_KELVIN),
            self.min_color_temp_mireds,
            self.max_color_temp_mireds,
        )
        brightness = normalize_hue_brightness(kwargs.get(ATTR_BRIGHTNESS))
        if self._last_brightness and brightness is None:
            # The Hue bridge sets the brightness to 1% when turning on a bulb
            # when a transition was used to turn off the bulb.
            # This issue has been reported on the Hue forum several times:
            # https://developers.meethue.com/forum/t/brightness-turns-down-to-1-automatically-shortly-after-sending-off-signal-hue-bug/5692
            # https://developers.meethue.com/forum/t/lights-turn-on-with-lowest-brightness-via-siri-if-turned-off-via-api/6700
            # https://developers.meethue.com/forum/t/using-transitiontime-with-on-false-resets-bri-to-1/4585
            # https://developers.meethue.com/forum/t/bri-value-changing-in-switching-lights-on-off/6323
            # https://developers.meethue.com/forum/t/fade-in-fade-out/6673
            brightness = self._last_brightness
            self._last_brightness = None
        self._color_temp_active = color_temp is not None
        flash = kwargs.get(ATTR_FLASH)
        effect = effect_str = kwargs.get(ATTR_EFFECT)
        if effect_str == EFFECT_OFF:
            # ignore effect if set to "off" and we have no effect active
            # the special effect "off" is only used to stop an active effect
            # but sending it while no effect is active can actually result in issues
            # https://github.com/home-assistant/core/issues/122165
            effect = None if self.effect == EFFECT_OFF else EffectStatus.NO_EFFECT
        elif effect_str is not None:
            # work out if we got a regular effect or timed effect
            effect = EffectStatus(effect_str)
            if effect == EffectStatus.UNKNOWN:
                effect = TimedEffectStatus(effect_str)
                if transition is None:
                    # a transition is required for timed effect, default to 10 minutes
                    transition = 600000
                # timed effects have no color parameters
                color_temp = None
                xy_color = None

        if flash is not None:
            await self.async_set_flash(flash)
            # flash cannot be sent with other commands at the same
            # time or result will be flaky. Hue's default behavior
            # is that a light returns to its previous state for
            # short flash (identify) and the light is kept turned
            # on for long flash (breathe effect)
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

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        transition = normalize_hue_transition(kwargs.get(ATTR_TRANSITION))
        if transition is not None and self.resource.dimming:
            self._last_brightness = self.resource.dimming.brightness
        flash = kwargs.get(ATTR_FLASH)

        if flash is not None:
            await self.async_set_flash(flash)
            # flash cannot be sent with other commands at the same
            # time or result will be flaky. Hue's default behavior
            # is that a light returns to its previous state for
            # short flash (identify) and the light is kept turned
            # on for long flash (breathe effect)
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


# pylint: disable-next=home-assistant-enforce-class-module
class HueGradientSegmentLight(HueBaseEntity, LightEntity):
    """One color point of a Hue gradient light.

    On/off and brightness apply to the whole light, as the Hue API has no
    per-point control for them. Segments are hidden by default.
    """

    entity_description = LightEntityDescription(
        key="hue_gradient_segment",
        translation_key="gradient_segment",
        has_entity_name=True,
    )
    _attr_color_mode = ColorMode.XY
    _attr_supported_color_modes = {ColorMode.XY}
    _attr_supported_features = LightEntityFeature.TRANSITION
    # area and device targets skip hidden entities, so whole-room commands
    # reach only the main light instead of fanning out to every segment
    _attr_entity_registry_visible_default = False

    def __init__(
        self,
        bridge: HueBridge,
        controller: LightsController,
        resource: Light,
        writer: HueGradientWriter,
        number: int,
    ) -> None:
        """Initialize the segment light."""
        super().__init__(bridge, controller, resource)
        self.resource = resource
        self._writer = writer
        self._index = number - 1
        self._attr_unique_id = gradient_segment_unique_id(resource, number)
        self._attr_translation_placeholders = {"segment": str(number)}

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self.resource.on.on

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of the light between 0..255."""
        if dimming := self.resource.dimming:
            return hue_brightness_to_ha(dimming.brightness)
        return None

    @property
    @override
    def xy_color(self) -> tuple[float, float]:
        """Return the xy color of this segment."""
        return gradient_point_color(self.resource, self._index)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, setting the color of this segment when given."""
        point = None
        if (xy_color := kwargs.get(ATTR_XY_COLOR)) is not None:
            point = (self._index, xy_color)
        await self._writer.async_set_state(
            on=True,
            brightness=normalize_hue_brightness(kwargs.get(ATTR_BRIGHTNESS)),
            transition=normalize_hue_transition(kwargs.get(ATTR_TRANSITION)),
            point=point,
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._writer.async_set_state(
            on=False,
            brightness=None,
            transition=normalize_hue_transition(kwargs.get(ATTR_TRANSITION)),
        )

    @callback
    @override
    def on_update(self) -> None:
        """Handle a state update of the light reported by the bridge."""
        self._writer.resource_updated()


class HueGradientWriter:
    """Write the state of the segments of a gradient light to the bridge.

    The segments share one light resource, so writes to several segments at
    the same time are merged into a single request. Colors are sent as the
    full list of gradient points.
    """

    def __init__(
        self, bridge: HueBridge, controller: LightsController, resource: Light
    ) -> None:
        """Initialize the writer."""
        self._bridge = bridge
        self._controller = controller
        self._resource = resource
        self._pending_on: bool | None = None
        self._pending_points: dict[int, tuple[float, float]] = {}
        self._pending_brightness: float | None = None
        self._pending_transition: float | None = None
        self._written_points: list[tuple[float, float]] | None = None
        self._flush_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def async_set_state(
        self,
        on: bool,
        brightness: float | None,
        transition: float | None,
        point: tuple[int, tuple[float, float]] | None = None,
    ) -> None:
        """Set the light state, optionally with the color of one gradient point.

        The write is sent together with writes of other segments made at the
        same time.
        """
        self._pending_on = on
        if point is not None:
            index, xy_color = point
            self._pending_points[index] = xy_color
        if brightness is not None:
            self._pending_brightness = brightness
        if transition is not None:
            self._pending_transition = transition
        if self._flush_task is None:
            self._flush_task = self._bridge.hass.async_create_task(self._async_flush())
        # shielded so a cancelled caller does not drop the writes of the others
        await asyncio.shield(self._flush_task)

    @callback
    def resource_updated(self) -> None:
        """Handle a state update of the light reported by the bridge."""
        self._written_points = None

    async def _async_flush(self) -> None:
        """Send the pending state to the bridge after the coalescing window."""
        await asyncio.sleep(GRADIENT_COALESCE_DELAY)
        # requests go out one at a time so each builds on the result of the last
        async with self._lock:
            # take the pending state before the request so writes arriving while
            # it is in flight start a new flush instead of getting lost
            on, self._pending_on = self._pending_on, None
            points, self._pending_points = self._pending_points, {}
            brightness, self._pending_brightness = self._pending_brightness, None
            transition, self._pending_transition = self._pending_transition, None
            self._flush_task = None
            gradient_points = None
            gradient_mode = None
            if points:
                gradient = self._resource.gradient
                # the resource only reflects a write once the bridge reports it
                # back, so until then the last written points are the baseline
                if (baseline := self._written_points) is None:
                    baseline = [
                        gradient_point_color(self._resource, index)
                        for index in range(gradient.points_capable)
                    ]
                gradient_points = [
                    points.get(index, color) for index, color in enumerate(baseline)
                ]
                # the bridge resets the mode to interpolated when it is omitted
                gradient_mode = gradient.mode
            await self._bridge.async_request_call(
                self._controller.set_state,
                id=self._resource.id,
                on=on,
                brightness=brightness,
                transition_time=transition,
                gradient_points=gradient_points,
                gradient_mode=gradient_mode,
            )
            if gradient_points is not None:
                self._written_points = gradient_points
