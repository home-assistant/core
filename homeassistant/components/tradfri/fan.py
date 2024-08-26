"""Represent an air purifier."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from pytradfri.command import Command

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import TradfriBaseEntity
from .const import CONF_GATEWAY_ID, COORDINATOR, COORDINATOR_LIST, DOMAIN, KEY_API
from .coordinator import TradfriDeviceDataUpdateCoordinator

ATTR_AUTO = "Auto"
ATTR_MAX_FAN_STEPS = 49


def _from_fan_percentage(percentage: int) -> int:
    """Convert percent to a value that the Tradfri API understands."""
    return round(max(2, (percentage / 100 * ATTR_MAX_FAN_STEPS) + 1))


def _from_fan_speed(fan_speed: int) -> int:
    """Convert the Tradfri API fan speed to a percentage value."""
    return max(round((fan_speed - 1) / ATTR_MAX_FAN_STEPS * 100), 0)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Tradfri switches based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    coordinator_data = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    api = coordinator_data[KEY_API]

    async_add_entities(
        TradfriAirPurifierFan(
            device_coordinator,
            api,
            gateway_id,
        )
        for device_coordinator in coordinator_data[COORDINATOR_LIST]
        if device_coordinator.device.has_air_purifier_control
    )


class TradfriAirPurifierFan(TradfriBaseEntity, FanEntity):
    """The platform class required by Home Assistant."""

    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = [ATTR_AUTO]
    # These are the steps:
    # 0 = Off
    # 1 = Preset: Auto mode
    # 2 = Min
    # ... with step size 1
    # 50 = Max
    _attr_speed_count = ATTR_MAX_FAN_STEPS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        device_coordinator: TradfriDeviceDataUpdateCoordinator,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
    ) -> None:
        """Initialize a switch."""
        super().__init__(
            device_coordinator=device_coordinator,
            api=api,
            gateway_id=gateway_id,
        )

        self._device_control = self._device.air_purifier_control
        self._device_data = self._device_control.air_purifiers[0]

    def _refresh(self) -> None:
        """Refresh the device."""
        self._device_data = self.coordinator.data.air_purifier_control.air_purifiers[0]

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if not self._device_data:
            return False
        return cast(bool, self._device_data.state)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self._device_data:
            return None

        if self._device_data.fan_speed:
            return _from_fan_speed(self._device_data.fan_speed)

        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if not self._device_data:
            return None

        if self._device_data.is_auto_mode:
            return ATTR_AUTO

        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if not self._device_control:
            return

        # Preset must be 'Auto'

        await self._api(self._device_control.turn_on_auto_mode())

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan. Auto-mode if no argument is given."""
        if not self._device_control:
            return

        if percentage is not None:
            await self.async_set_percentage(percentage)
            return

        preset_mode = preset_mode or ATTR_AUTO
        await self.async_set_preset_mode(preset_mode)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if not self._device_control:
            return

        if percentage == 0:
            await self.async_turn_off()
            return

        await self._api(
            self._device_control.set_fan_speed(_from_fan_percentage(percentage))
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        if not self._device_control:
            return
        await self._api(self._device_control.turn_off())
