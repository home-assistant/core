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
    ATTR_FLASH,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_XY,
    FLASH_SHORT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    LightEntity,
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
        if self.resource.alert and self.resource.alert.action_values:
            self._attr_supported_features |= SUPPORT_FLASH
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
        self._last_xy: tuple[float, float] | None = self.xy_color
        self._last_color_temp: int = self.color_temp
        self._set_color_mode()

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

    @callback
    def on_update(self) -> None:
        """Call on update event."""
        self._set_color_mode()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        transition = normalize_hue_transition(kwargs.get(ATTR_TRANSITION))
        xy_color = kwargs.get(ATTR_XY_COLOR)
        color_temp = normalize_hue_colortemp(kwargs.get(ATTR_COLOR_TEMP))
        brightness = normalize_hue_brightness(kwargs.get(ATTR_BRIGHTNESS))
        flash = kwargs.get(ATTR_FLASH)

        if flash is not None:
            await self.async_set_flash(flash)
            # flash can not be sent with other commands at the same time or result will be flaky
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
            allowed_errors=ALLOWED_ERRORS,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        transition = normalize_hue_transition(kwargs.get(ATTR_TRANSITION))
        flash = kwargs.get(ATTR_FLASH)

        if flash is not None:
            await self.async_set_flash(flash)
            # flash can not be sent with other commands at the same time or result will be flaky
            # Hue's default behavior is that a light returns to its previous state for short
            # flash (identify) and the light is kept turned on for long flash (breathe effect)
            return

        await self.bridge.async_request_call(
            self.controller.set_state,
            id=self.resource.id,
            on=False,
            transition_time=transition,
            allowed_errors=ALLOWED_ERRORS,
        )

    async def async_set_flash(self, flash: str) -> None:
        """Send flash command to light."""
        await self.bridge.async_request_call(
            self.controller.set_flash,
            id=self.resource.id,
            short=flash == FLASH_SHORT,
        )

    @callback
    def _set_color_mode(self) -> None:
        """Set current colormode of light."""
        last_xy = self._last_xy
        last_color_temp = self._last_color_temp
        self._last_xy = self.xy_color
        self._last_color_temp = self.color_temp

        # Certified Hue lights return `mired_valid` to indicate CT is active
        if color_temp := self.resource.color_temperature:
            if color_temp.mirek_valid and color_temp.mirek is not None:
                self._attr_color_mode = COLOR_MODE_COLOR_TEMP
                return

        # Non-certified lights do not report their current color mode correctly
        # so we keep track of the color values to determine which is active
        if last_color_temp != self.color_temp:
            self._attr_color_mode = COLOR_MODE_COLOR_TEMP
            return
        if last_xy != self.xy_color:
            self._attr_color_mode = COLOR_MODE_XY
            return

        # if we didn't detect any changes, abort and use previous values
        if self._attr_color_mode is not None:
            return

        # color mode not yet determined, work it out here
        # Note that for lights that do not correctly report `mirek_valid`
        # we might have an invalid startup state which will be auto corrected
        if self.resource.supports_color:
            self._attr_color_mode = COLOR_MODE_XY
        elif self.resource.supports_color_temperature:
            self._attr_color_mode = COLOR_MODE_COLOR_TEMP
        elif self.resource.supports_dimming:
            self._attr_color_mode = COLOR_MODE_BRIGHTNESS
        else:
            # fallback to on_off
            self._attr_color_mode = COLOR_MODE_ONOFF
