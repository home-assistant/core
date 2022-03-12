"""Support for IKEA Tradfri lights."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from pytradfri.command import Command

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from .base_class import TradfriBaseEntity
from .const import (
    ATTR_DIMMER,
    ATTR_HUE,
    ATTR_SAT,
    ATTR_TRANSITION_TIME,
    CONF_GATEWAY_ID,
    COORDINATOR,
    COORDINATOR_LIST,
    DOMAIN,
    KEY_API,
    SUPPORTED_LIGHT_FEATURES,
)
from .coordinator import TradfriDeviceDataUpdateCoordinator


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
        [
            TradfriLight(
                device_coordinator,
                api,
                gateway_id,
            )
            for device_coordinator in coordinator_data[COORDINATOR_LIST]
            if device_coordinator.device.has_light_control
        ]
    )


class TradfriLight(TradfriBaseEntity, LightEntity):
    """The platform class required by Home Assistant."""

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

        # Calculate supported features
        _features = SUPPORTED_LIGHT_FEATURES
        if self._device.light_control.can_set_dimmer:
            _features |= SUPPORT_BRIGHTNESS
        if self._device.light_control.can_set_color:
            _features |= SUPPORT_COLOR | SUPPORT_COLOR_TEMP
        if self._device.light_control.can_set_temp:
            _features |= SUPPORT_COLOR_TEMP
        self._attr_supported_features = _features

        if self._device_control:
            self._attr_min_mireds = self._device_control.min_mireds
            self._attr_max_mireds = self._device_control.max_mireds

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
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if not self._device_data:
            return None
        return cast(int, self._device_data.dimmer)

    @property
    def color_temp(self) -> int | None:
        """Return the color temp value in mireds."""
        if not self._device_data:
            return None
        return cast(int, self._device_data.color_temp)

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

            dimmer_data = {ATTR_DIMMER: 0, ATTR_TRANSITION_TIME: transition_time}
            await self._api(self._device_control.set_dimmer(**dimmer_data))
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
                ATTR_DIMMER: brightness,
                ATTR_TRANSITION_TIME: transition_time,
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
                ATTR_HUE: hue,
                ATTR_SAT: sat,
                ATTR_TRANSITION_TIME: transition_time,
            }
            color_command = self._device_control.set_hsb(**color_data)
            transition_time = None

        temp_command = None
        if ATTR_COLOR_TEMP in kwargs and (
            self._device_control.can_set_temp or self._device_control.can_set_color
        ):
            temp = kwargs[ATTR_COLOR_TEMP]
            # White Spectrum bulb
            if self._device_control.can_set_temp:
                if temp > self.max_mireds:
                    temp = self.max_mireds
                elif temp < self.min_mireds:
                    temp = self.min_mireds
                temp_data = {
                    ATTR_COLOR_TEMP: temp,
                    ATTR_TRANSITION_TIME: transition_time,
                }
                temp_command = self._device_control.set_color_temp(**temp_data)
                transition_time = None
            # Color bulb (CWS)
            # color_temp needs to be set with hue/saturation
            elif self._device_control.can_set_color:
                temp_k = color_util.color_temperature_mired_to_kelvin(temp)
                hs_color = color_util.color_temperature_to_hs(temp_k)
                hue = int(hs_color[0] * (self._device_control.max_hue / 360))
                sat = int(hs_color[1] * (self._device_control.max_saturation / 100))
                color_data = {
                    ATTR_HUE: hue,
                    ATTR_SAT: sat,
                    ATTR_TRANSITION_TIME: transition_time,
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
