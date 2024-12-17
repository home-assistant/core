"""Support for IKEA Tradfri lights."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from pytradfri.command import Command

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    filter_supported_color_modes,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from .const import CONF_GATEWAY_ID, COORDINATOR, COORDINATOR_LIST, DOMAIN, KEY_API
from .coordinator import TradfriDeviceDataUpdateCoordinator
from .entity import TradfriBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Tradfri lights based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    coordinator_data = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    api = coordinator_data[KEY_API]

    async_add_entities(
        TradfriLight(
            device_coordinator,
            api,
            gateway_id,
        )
        for device_coordinator in coordinator_data[COORDINATOR_LIST]
        if device_coordinator.device.has_light_control
    )


class TradfriLight(TradfriBaseEntity, LightEntity):
    """The platform class required by Home Assistant."""

    _attr_name = None
    _attr_supported_features = LightEntityFeature.TRANSITION
    _fixed_color_mode: ColorMode | None = None

    def __init__(
        self,
        device_coordinator: TradfriDeviceDataUpdateCoordinator,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
    ) -> None:
        """Initialize a Light."""
        super().__init__(
            device_coordinator=device_coordinator,
            api=api,
            gateway_id=gateway_id,
        )

        self._device_control = self._device.light_control
        self._device_data = self._device_control.lights[0]

        self._attr_unique_id = f"light-{gateway_id}-{self._device_id}"
        self._hs_color = None

        # Calculate supported color modes
        modes: set[ColorMode] = {ColorMode.ONOFF}
        if self._device.light_control.can_set_color:
            modes.add(ColorMode.HS)
        if self._device.light_control.can_set_temp:
            modes.add(ColorMode.COLOR_TEMP)
        if self._device.light_control.can_set_dimmer:
            modes.add(ColorMode.BRIGHTNESS)
        self._attr_supported_color_modes = filter_supported_color_modes(modes)
        if len(self._attr_supported_color_modes) == 1:
            self._fixed_color_mode = next(iter(self._attr_supported_color_modes))

        if self._device_control:
            self._attr_max_color_temp_kelvin = (
                color_util.color_temperature_mired_to_kelvin(
                    self._device_control.min_mireds
                )
            )
            self._attr_min_color_temp_kelvin = (
                color_util.color_temperature_mired_to_kelvin(
                    self._device_control.max_mireds
                )
            )

    def _refresh(self) -> None:
        """Refresh the device."""
        self._device_data = self.coordinator.data.light_control.lights[0]

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        if not self._device_data:
            return False
        return cast(bool, self._device_data.state)

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the color mode of the light."""
        if self._fixed_color_mode:
            return self._fixed_color_mode
        if self.hs_color:
            return ColorMode.HS
        return ColorMode.COLOR_TEMP

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if not self._device_data:
            return None
        return cast(int, self._device_data.dimmer)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature value in Kelvin."""
        if not self._device_data or not (color_temp := self._device_data.color_temp):
            return None
        return color_util.color_temperature_mired_to_kelvin(color_temp)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """HS color of the light."""
        if not self._device_control or not self._device_data:
            return None
        if self._device_control.can_set_color:
            hsbxy = self._device_data.hsb_xy_color
            hue = hsbxy[0] / (self._device_control.max_hue / 360)
            sat = hsbxy[1] / (self._device_control.max_saturation / 100)
            if hue is not None and sat is not None:
                return hue, sat
        return None

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        # This allows transitioning to off, but resets the brightness
        # to 1 for the next set_state(True) command
        if not self._device_control:
            return
        transition_time = None
        if ATTR_TRANSITION in kwargs:
            transition_time = int(kwargs[ATTR_TRANSITION]) * 10

            await self._api(
                self._device_control.set_dimmer(
                    dimmer=0, transition_time=transition_time
                )
            )
        else:
            await self._api(self._device_control.set_state(False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if not self._device_control:
            return
        transition_time = None
        if ATTR_TRANSITION in kwargs:
            transition_time = int(kwargs[ATTR_TRANSITION]) * 10

        dimmer_command = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = min(brightness, 254)
            dimmer_data = {
                "dimmer": brightness,
                "transition_time": transition_time,
            }
            dimmer_command = self._device_control.set_dimmer(**dimmer_data)
            transition_time = None
        else:
            dimmer_command = self._device_control.set_state(True)

        color_command = None
        if ATTR_HS_COLOR in kwargs and self._device_control.can_set_color:
            hue = int(kwargs[ATTR_HS_COLOR][0] * (self._device_control.max_hue / 360))
            sat = int(
                kwargs[ATTR_HS_COLOR][1] * (self._device_control.max_saturation / 100)
            )
            color_data = {
                "hue": hue,
                "saturation": sat,
                "transition_time": transition_time,
            }
            color_command = self._device_control.set_hsb(**color_data)
            transition_time = None

        temp_command = None
        if ATTR_COLOR_TEMP_KELVIN in kwargs and (
            self._device_control.can_set_temp or self._device_control.can_set_color
        ):
            temp_k = kwargs[ATTR_COLOR_TEMP_KELVIN]
            # White Spectrum bulb
            if self._device_control.can_set_temp:
                temp = color_util.color_temperature_kelvin_to_mired(temp_k)
                if temp < (min_mireds := self._device_control.min_mireds):
                    temp = min_mireds
                elif temp > (max_mireds := self._device_control.max_mireds):
                    temp = max_mireds
                temp_data = {
                    "color_temp": temp,
                    "transition_time": transition_time,
                }
                temp_command = self._device_control.set_color_temp(**temp_data)
                transition_time = None
            # Color bulb (CWS)
            # color_temp needs to be set with hue/saturation
            elif self._device_control.can_set_color:
                hs_color = color_util.color_temperature_to_hs(temp_k)
                hue = int(hs_color[0] * (self._device_control.max_hue / 360))
                sat = int(hs_color[1] * (self._device_control.max_saturation / 100))
                color_data = {
                    "hue": hue,
                    "saturation": sat,
                    "transition_time": transition_time,
                }
                color_command = self._device_control.set_hsb(**color_data)
                transition_time = None

        # HSB can always be set, but color temp + brightness is bulb dependent
        if (command := dimmer_command) is not None:
            command += color_command
        else:
            command = color_command

        if self._device_control.can_combine_commands:
            await self._api(command + temp_command)
        else:
            if temp_command is not None:
                await self._api(temp_command)
            if command is not None:
                await self._api(command)
