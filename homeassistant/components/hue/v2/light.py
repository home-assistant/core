"""Support for Hue lights."""
from __future__ import annotations

from typing import Any

from aiohue import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.lights import LightsController
from aiohue.v2.models.light import Light

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
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..bridge import HueBridge
from ..const import DOMAIN
from .entity import HueBaseEntity

ALLOWED_ERRORS = [
    "device (light) has communication issues, command (on) may not have effect",
    'device (light) is "soft off", command (on) may not have effect',
]


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
        self.resource = resource
        self.controller = controller
        self._supported_color_modes = set()
        if self.resource.supports_color:
            self._supported_color_modes.add(COLOR_MODE_XY)
        if self.resource.supports_color_temperature:
            self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
        if self.resource.supports_dimming:
            if len(self._supported_color_modes) == 0:
                # only add color mode brightness if no color variants
                self._supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
            # support transition if brightness control
            self._attr_supported_features |= SUPPORT_TRANSITION

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if dimming := self.resource.dimming:
            # Hue uses a range of [0, 100] to control brightness.
            return round((dimming.brightness / 100) * 255)
        return None

    @property
    def color_mode(self) -> str:
        """Return the current color mode of the light."""
        if color_temp := self.resource.color_temperature:
            if color_temp.mirek_valid and color_temp.mirek is not None:
                return COLOR_MODE_COLOR_TEMP
        if self.resource.supports_color:
            return COLOR_MODE_XY
        if self.resource.supports_dimming:
            return COLOR_MODE_BRIGHTNESS
        return COLOR_MODE_ONOFF

    @property
    def is_on(self) -> bool:
        """Return true if device is on (brightness above 0)."""
        return self.resource.on.on

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
        return 0

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        if color_temp := self.resource.color_temperature:
            return color_temp.mirek_schema.mirek_minimum
        return 0

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        if color_temp := self.resource.color_temperature:
            return color_temp.mirek_schema.mirek_maximum
        return 0

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
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

        await self.bridge.async_request_call(
            self.controller.set_state,
            id=self.resource.id,
            on=True,
            brightness=brightness,
            color_xy=xy_color,
            color_temp=color_temp,
            transition_time=transition,
            allowed_errors=ALLOWED_ERRORS,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        transition = kwargs.get(ATTR_TRANSITION)
        if transition is not None:
            # hue transition duration is in steps of 100 ms
            transition = int(transition * 100)
        await self.bridge.async_request_call(
            self.controller.set_state,
            id=self.resource.id,
            on=False,
            transition_time=transition,
            allowed_errors=ALLOWED_ERRORS,
        )
