"""Support for HUE groups (room/zone)."""
from __future__ import annotations

from typing import Any

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.groups import GroupedLightController
from aiohue.v2.models.grouped_light import GroupedLight

from homeassistant.components.group.light import LightGroup
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_XY,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..bridge import HueBridge
from ..const import DOMAIN
from .entity import HueBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hue groups on light platform."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: HueBridgeV2 = bridge.api
    controller: GroupedLightController = api.groups.grouped_light

    @callback
    def async_add_grouped_light(event_type:EventType, resource: GroupedLight) -> None:
        """Add HUE Grouped Light."""
        if controller.get_zone(resource.id) is None:
            # filter out special "all lights" group
            return
        light = GroupedHueLight(bridge, controller, resource)
        async_add_entities([light])

    for light in controller:
        async_add_grouped_light(EventType.RESOURCE_ADDED, light)

    # register listener for new lights
    config_entry.async_on_unload(
        controller.subscribe(
            async_add_grouped_light, event_filter=EventType.RESOURCE_ADDED
        )
    )


class GroupedHueLight(HueBaseEntity, LightGroup):
    """Representation of a Grouped Hue light."""

    def __init__(
        self,
        bridge: HueBridge,
        controller: GroupedLightController,
        resource: GroupedLight,
    ) -> None:
        """Initialize the light."""
        super().__init__(bridge, controller, resource)
        self.resource = resource
        self.controller = controller
        self.api: HueBridgeV2 = bridge.api
        self._update_values()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        await super().async_added_to_hass()

        # We need to watch the underlying lights too
        # if we want feedback about color/brightness changes
        if self._attr_supported_color_modes:
            light_ids = tuple(
                x.id for x in self.controller.get_lights(self.resource.id)
            )
            self.async_on_remove(
                self.api.lights.subscribe(self._handle_event, light_ids)
            )

    @property
    def name(self) -> str:
        """Return name of room/zone for this grouped light."""
        if zone := self.controller.get_zone(self.resource.id):
            return zone.metadata.name
        return ""

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.resource.on.on

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
        if zone := self.controller.get_zone(self.resource.id):
            scenes = {
                x.metadata.name for x in self.api.scenes if x.group.rid == zone.id
            }
        else:
            scenes = set()
        return {
            "is_hue_group": True,
            "hue_scenes": scenes,
            "hue_type": zone.type.value if zone else "",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        transition = kwargs.get(ATTR_TRANSITION)
        xy_color = kwargs.get(ATTR_XY_COLOR)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            # Hue uses a range of [0, 100] to control brightness.
            brightness = round((brightness / 255) * 100)

        await self.controller.set_state(
            id=self.resource.id,
            on=True,
            brightness=brightness,
            color_xy=xy_color,
            color_temp=color_temp,
            transition_time=transition,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.controller.set_state(id=self.resource.id, on=False)

    @callback
    def on_update(self) -> None:
        """Call on update event."""
        self._update_values()

    @callback
    def _update_values(self) -> None:
        """Set base values from underlying lights of a group."""
        supported_color_modes = set()
        lights_with_color_support = 0
        lights_with_color_temp_support = 0
        lights_with_dimming_support = 0
        total_brightness = 0
        all_lights = self.controller.get_lights(self.resource.id)
        lights_in_colortemp_mode = 0
        # loop through all lights to find capabilities
        for light in all_lights:
            if color_temp := light.color_temperature:
                lights_with_color_temp_support += 1
                # we assume mired values from the first capable light
                self._attr_color_temp = color_temp.mirek
                self._attr_max_mireds = color_temp.mirek_schema.mirek_maximum
                self._attr_min_mireds = color_temp.mirek_schema.mirek_minimum
                if color_temp.mirek is not None and color_temp.mirek_valid:
                    lights_in_colortemp_mode += 1
            if color := light.color:
                lights_with_color_support += 1
                # we assume xy values from the first capable light
                self._attr_xy_color = (color.xy.x, color.xy.y)
            if dimming := light.dimming:
                lights_with_dimming_support += 1
                total_brightness += dimming.brightness
        # this is a bit hacky because light groups may contain lights
        # of different capabilities. We set a colormode as supported
        # if any of the lights support it
        # this means that the state is derived from only some of the lights
        # and will never be 100% accurate but it will be close
        if lights_with_color_support > 0:
            supported_color_modes.add(COLOR_MODE_XY)
        if lights_with_color_temp_support > 0:
            supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
        if lights_with_dimming_support > 0:
            supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
            self._attr_brightness = round(
                ((total_brightness / lights_with_dimming_support) / 100) * 255
            )
        self._attr_supported_color_modes = supported_color_modes
        # pick a winner for the current colormode
        if lights_in_colortemp_mode == lights_with_color_temp_support:
            self._attr_color_mode = COLOR_MODE_COLOR_TEMP
        elif lights_with_color_support > 0:
            self._attr_color_mode = COLOR_MODE_XY
        elif lights_with_dimming_support > 0:
            self._attr_color_mode = COLOR_MODE_BRIGHTNESS
        else:
            self._attr_color_mode = None
