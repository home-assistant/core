"""Support for Hue groups (room/zone)."""
from __future__ import annotations

from typing import Any

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.groups import GroupedLight, Room, Zone

from homeassistant.components.group.light import LightGroup
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_XY,
    SUPPORT_TRANSITION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..bridge import HueBridge
from ..const import DOMAIN
from .entity import HueBaseEntity

ALLOWED_ERRORS = [
    "device (groupedLight) has communication issues, command (on) may not have effect",
    'device (groupedLight) is "soft off", command (on) may not have effect',
    "device (light) has communication issues, command (on) may not have effect",
    'device (light) is "soft off", command (on) may not have effect',
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hue groups on light platform."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: HueBridgeV2 = bridge.api

    # to prevent race conditions (groupedlight is created before zone/room)
    # we create groupedlights from the room/zone and actually use the
    # underlying grouped_light resource for control

    @callback
    def async_add_light(event_type: EventType, resource: Room | Zone) -> None:
        """Add Grouped Light for Hue Room/Zone."""
        if grouped_light_id := resource.grouped_light:
            grouped_light = api.groups.grouped_light[grouped_light_id]
            light = GroupedHueLight(bridge, grouped_light, resource)
            async_add_entities([light])

    # add current items
    for item in api.groups.room.items + api.groups.zone.items:
        async_add_light(EventType.RESOURCE_ADDED, item)

    # register listener for new zones/rooms
    config_entry.async_on_unload(
        api.groups.room.subscribe(
            async_add_light, event_filter=EventType.RESOURCE_ADDED
        )
    )
    config_entry.async_on_unload(
        api.groups.zone.subscribe(
            async_add_light, event_filter=EventType.RESOURCE_ADDED
        )
    )


class GroupedHueLight(HueBaseEntity, LightGroup):
    """Representation of a Grouped Hue light."""

    # Entities for Hue groups are disabled by default
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, bridge: HueBridge, resource: GroupedLight, group: Room | Zone
    ) -> None:
        """Initialize the light."""
        controller = bridge.api.groups.grouped_light
        super().__init__(bridge, controller, resource)
        self.resource = resource
        self.group = group
        self.controller = controller
        self.api: HueBridgeV2 = bridge.api
        self._attr_supported_features |= SUPPORT_TRANSITION

        self._update_values()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        await super().async_added_to_hass()

        # subscribe to group updates
        self.async_on_remove(
            self.api.groups.subscribe(self._handle_event, self.group.id)
        )
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
        return self.group.metadata.name

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.resource.on.on

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
        scenes = {
            x.metadata.name for x in self.api.scenes if x.group.rid == self.group.id
        }
        lights = {x.metadata.name for x in self.controller.get_lights(self.resource.id)}
        return {
            "is_hue_group": True,
            "hue_scenes": scenes,
            "hue_type": self.group.type.value,
            "lights": lights,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        transition = kwargs.get(ATTR_TRANSITION)
        xy_color = kwargs.get(ATTR_XY_COLOR)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            # Hue uses a range of [0, 100] to control brightness.
            brightness = float((brightness / 255) * 100)
        if transition is not None:
            # hue transition duration is in steps of 100 ms
            transition = int(transition * 100)

        # NOTE: a grouped_light can only handle turn on/off
        # To set other features, you'll have to control the attached lights
        if (
            brightness is None
            and xy_color is None
            and color_temp is None
            and transition is None
        ):
            await self.bridge.async_request_call(
                self.controller.set_state,
                id=self.resource.id,
                on=True,
                allowed_errors=ALLOWED_ERRORS,
            )
            return

        # redirect all other feature commands to underlying lights
        # note that this silently ignores params sent to light that are not supported
        for light in self.controller.get_lights(self.resource.id):
            await self.bridge.async_request_call(
                self.api.lights.set_state,
                light.id,
                on=True,
                brightness=brightness if light.supports_dimming else None,
                color_xy=xy_color if light.supports_color else None,
                color_temp=color_temp if light.supports_color_temperature else None,
                transition_time=transition,
                allowed_errors=ALLOWED_ERRORS,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.bridge.async_request_call(
            self.controller.set_state,
            id=self.resource.id,
            on=False,
            allowed_errors=ALLOWED_ERRORS,
        )

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
            if len(supported_color_modes) == 0:
                # only add color mode brightness if no color variants
                supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
            self._attr_brightness = round(
                ((total_brightness / lights_with_dimming_support) / 100) * 255
            )
        else:
            supported_color_modes.add(COLOR_MODE_ONOFF)
        self._attr_supported_color_modes = supported_color_modes
        # pick a winner for the current colormode
        if lights_in_colortemp_mode == lights_with_color_temp_support:
            self._attr_color_mode = COLOR_MODE_COLOR_TEMP
        elif lights_with_color_support > 0:
            self._attr_color_mode = COLOR_MODE_XY
        elif lights_with_dimming_support > 0:
            self._attr_color_mode = COLOR_MODE_BRIGHTNESS
        else:
            self._attr_color_mode = COLOR_MODE_ONOFF
