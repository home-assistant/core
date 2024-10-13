"""Support for Hue groups (room/zone)."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.groups import GroupedLight, Room, Zone
from aiohue.v2.models.feature import DynamicStatus

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_FLASH,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    FLASH_SHORT,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er

from ..bridge import HueBridge
from ..const import DOMAIN
from .entity import HueBaseEntity
from .helpers import (
    normalize_hue_brightness,
    normalize_hue_colortemp,
    normalize_hue_transition,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hue groups on light platform."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: HueBridgeV2 = bridge.api

    async def async_add_light(event_type: EventType, resource: GroupedLight) -> None:
        """Add Grouped Light for Hue Room/Zone."""
        # delay group creation a bit due to a race condition where the
        # grouped_light resource is created before the zone/room
        retries = 5
        while (
            retries
            and (group := api.groups.grouped_light.get_zone(resource.id)) is None
        ):
            retries -= 1
            await asyncio.sleep(0.5)
        if group is None:
            # guard, just in case
            return
        light = GroupedHueLight(bridge, resource, group)
        async_add_entities([light])

    # add current items
    for item in api.groups.grouped_light.items:
        await async_add_light(EventType.RESOURCE_ADDED, item)

    # register listener for new grouped_light
    config_entry.async_on_unload(
        api.groups.grouped_light.subscribe(
            async_add_light, event_filter=EventType.RESOURCE_ADDED
        )
    )


# pylint: disable-next=hass-enforce-class-module
class GroupedHueLight(HueBaseEntity, LightEntity):
    """Representation of a Grouped Hue light."""

    entity_description = LightEntityDescription(
        key="hue_grouped_light",
        icon="mdi:lightbulb-group",
        has_entity_name=True,
        name=None,
    )

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
        self._attr_supported_features |= LightEntityFeature.FLASH
        self._attr_supported_features |= LightEntityFeature.TRANSITION
        self._restore_brightness: float | None = None
        self._brightness_pct: float = 0
        # we create a virtual service/device for Hue zones/rooms
        # so we have a parent for grouped lights and scenes
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.group.id)},
        )
        self._dynamic_mode_active = False
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
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.resource.on.on

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
        scenes = {
            x.metadata.name for x in self.api.scenes if x.group.rid == self.group.id
        }
        light_resource_ids = tuple(
            x.id for x in self.controller.get_lights(self.resource.id)
        )
        light_names, light_entities = self._get_names_and_entity_ids_for_resource_ids(
            light_resource_ids
        )
        return {
            "is_hue_group": True,
            "hue_scenes": scenes,
            "hue_type": self.group.type.value,
            "lights": light_names,
            "entity_id": light_entities,
            "dynamics": self._dynamic_mode_active,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the grouped_light on."""
        transition = normalize_hue_transition(kwargs.get(ATTR_TRANSITION))
        xy_color = kwargs.get(ATTR_XY_COLOR)
        color_temp = normalize_hue_colortemp(kwargs.get(ATTR_COLOR_TEMP))
        brightness = normalize_hue_brightness(kwargs.get(ATTR_BRIGHTNESS))
        flash = kwargs.get(ATTR_FLASH)

        if self._restore_brightness and brightness is None:
            # The Hue bridge sets the brightness to 1% when turning on a bulb
            # when a transition was used to turn off the bulb.
            # This issue has been reported on the Hue forum several times:
            # https://developers.meethue.com/forum/t/brightness-turns-down-to-1-automatically-shortly-after-sending-off-signal-hue-bug/5692
            # https://developers.meethue.com/forum/t/lights-turn-on-with-lowest-brightness-via-siri-if-turned-off-via-api/6700
            # https://developers.meethue.com/forum/t/using-transitiontime-with-on-false-resets-bri-to-1/4585
            # https://developers.meethue.com/forum/t/bri-value-changing-in-switching-lights-on-off/6323
            # https://developers.meethue.com/forum/t/fade-in-fade-out/6673
            brightness = self._restore_brightness
            self._restore_brightness = None

        if flash is not None:
            await self.async_set_flash(flash)
            return

        await self.bridge.async_request_call(
            self.controller.set_state,
            id=self.resource.id,
            on=True,
            brightness=brightness,
            color_xy=xy_color,
            color_temp=color_temp,
            transition_time=transition,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        transition = normalize_hue_transition(kwargs.get(ATTR_TRANSITION))
        if transition is not None:
            self._restore_brightness = self._brightness_pct
        flash = kwargs.get(ATTR_FLASH)

        if flash is not None:
            await self.async_set_flash(flash)
            # flash cannot be sent with other commands at the same time
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

    @callback
    def on_update(self) -> None:
        """Call on update event."""
        self._update_values()

    @callback
    def _update_values(self) -> None:
        """Set base values from underlying lights of a group."""
        supported_color_modes: set[ColorMode | str] = set()
        lights_with_color_support = 0
        lights_with_color_temp_support = 0
        lights_with_dimming_support = 0
        total_brightness = 0
        all_lights = self.controller.get_lights(self.resource.id)
        lights_in_colortemp_mode = 0
        lights_in_dynamic_mode = 0
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
            if (
                light.dynamics
                and light.dynamics.status == DynamicStatus.DYNAMIC_PALETTE
            ):
                lights_in_dynamic_mode += 1

        # this is a bit hacky because light groups may contain lights
        # of different capabilities. We set a colormode as supported
        # if any of the lights support it
        # this means that the state is derived from only some of the lights
        # and will never be 100% accurate but it will be close
        if lights_with_color_support > 0:
            supported_color_modes.add(ColorMode.XY)
        if lights_with_color_temp_support > 0:
            supported_color_modes.add(ColorMode.COLOR_TEMP)
        if lights_with_dimming_support > 0:
            if len(supported_color_modes) == 0:
                # only add color mode brightness if no color variants
                supported_color_modes.add(ColorMode.BRIGHTNESS)
            self._brightness_pct = total_brightness / lights_with_dimming_support
            self._attr_brightness = round(
                ((total_brightness / lights_with_dimming_support) / 100) * 255
            )
        else:
            supported_color_modes.add(ColorMode.ONOFF)
        self._dynamic_mode_active = lights_in_dynamic_mode > 0
        self._attr_supported_color_modes = supported_color_modes
        # pick a winner for the current colormode
        if lights_with_color_temp_support > 0 and lights_in_colortemp_mode > 0:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif lights_with_color_support > 0:
            self._attr_color_mode = ColorMode.XY
        elif lights_with_dimming_support > 0:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF

    @callback
    def _get_names_and_entity_ids_for_resource_ids(
        self, resource_ids: tuple[str]
    ) -> tuple[set[str], set[str]]:
        """Return the names and entity ids for the given Hue (light) resource IDs."""
        ent_reg = er.async_get(self.hass)
        light_names: set[str] = set()
        light_entities: set[str] = set()
        for resource_id in resource_ids:
            light_names.add(self.controller.get_device(resource_id).metadata.name)
            if entity_id := ent_reg.async_get_entity_id(
                self.platform.domain, DOMAIN, resource_id
            ):
                light_entities.add(entity_id)
        return light_names, light_entities
