"""Support for HUE lights."""
from __future__ import annotations

from typing import Any

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
    COLOR_MODE_XY,
    DOMAIN as LIGHT_DOMAIN,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..bridge import HueBridge
from ..const import DOMAIN, LOGGER
from .entity import HueBaseEntity

LOGGER = LOGGER.getChild(LIGHT_DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hue Light from Config Entry."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    controller: LightsController = bridge.api.lights

    @callback
    def async_add_light(event_type: EventType, resource: Light) -> None:
        """Add HUE Light."""
        light = HueLight(config_entry, controller, resource)
        async_add_entities([light])

    # add all current items in controller
    for light in controller:
        async_add_light(EventType.RESOURCE_ADDED, light)

    # register listener for new lights
    config_entry.async_on_unload(
        controller.subscribe(async_add_light, event_filter=EventType.RESOURCE_ADDED)
    )


class HueLight(HueBaseEntity, LightEntity):
    """Representation of a Hue light."""

    def __init__(
        self, config_entry: ConfigEntry, controller: LightsController, resource: Light
    ) -> None:
        """Initialize the light."""
        super().__init__(config_entry, controller, resource)
        self.resource = resource
        self.controller = controller
        self._supported_color_modes = set()
        if self.resource.supports_color:
            self._supported_color_modes.add(COLOR_MODE_XY)
        if self.resource.supports_color_temperature:
            self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
        if self.resource.supports_dimming:
            self._supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
            self._attr_supported_features |= SUPPORT_TRANSITION

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        if dimming := self.resource.dimming:
            # Hue uses a range of [0, 100] to control brightness.
            return round((dimming.brightness / 100) * 255)
        return None

    @property
    def color_mode(self) -> str | None:
        """Return the current color mode of the light."""
        if color_temp := self.resource.color_temperature:
            if color_temp.mirek_valid and color_temp.mirek is not None:
                return COLOR_MODE_COLOR_TEMP
        if self.resource.supports_color:
            return COLOR_MODE_XY
        if self.resource.supports_dimming:
            return COLOR_MODE_BRIGHTNESS
        return None

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
    def color_temp(self) -> int | None:
        """Return the color temperature."""
        if color_temp := self.resource.color_temperature:
            return color_temp.mirek
        return None

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        if color_temp := self.resource.color_temperature:
            return color_temp.mirek_schema.mirek_minimum
        return None

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        if color_temp := self.resource.color_temperature:
            return color_temp.mirek_schema.mirek_maximum
        return None

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
