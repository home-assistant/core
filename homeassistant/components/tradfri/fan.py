"""Represent an air purifier."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from pytradfri.command import Command

from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import TradfriBaseDevice
from .const import (
    ATTR_AUTO,
    ATTR_MAX_FAN_STEPS,
    CONF_GATEWAY_ID,
    DEVICES,
    DOMAIN,
    KEY_API,
)


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
    tradfri_data = hass.data[DOMAIN][config_entry.entry_id]
    api = tradfri_data[KEY_API]
    devices = tradfri_data[DEVICES]

    async_add_entities(
        TradfriAirPurifierFan(dev, api, gateway_id)
        for dev in devices
        if dev.has_air_purifier_control
    )


class TradfriAirPurifierFan(TradfriBaseDevice, FanEntity):
    """The platform class required by Home Assistant."""

    def __init__(
        self,
        device: Command,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
    ) -> None:
        """Initialize a switch."""
        super().__init__(device, api, gateway_id)
        self._attr_unique_id = f"{gateway_id}-{device.id}"
        self._refresh(device, write_ha=False)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_PRESET_MODE + SUPPORT_SET_SPEED

    @property
    def speed_count(self) -> int:
        """
        Return the number of speeds the fan supports.

        These are the steps:
        0 = Off
        1 = Preset: Auto mode
        2 = Min
        ... with step size 1
        50 = Max
        """
        return ATTR_MAX_FAN_STEPS

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if not self._device_data:
            return False
        return cast(bool, self._device_data.state)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        return [ATTR_AUTO]

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

        if not preset_mode == ATTR_AUTO:
            raise ValueError("Preset must be 'Auto'.")

        await self._api(self._device_control.turn_on_auto_mode())

    async def async_turn_on(
        self,
        speed: str | None = None,
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

    def _refresh(self, device: Command, write_ha: bool = True) -> None:
        """Refresh the purifier data."""
        # Caching of air purifier control and purifier object
        self._device_control = device.air_purifier_control
        self._device_data = device.air_purifier_control.air_purifiers[0]
        super()._refresh(device, write_ha=write_ha)
