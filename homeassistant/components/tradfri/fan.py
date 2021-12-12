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
from .const import ATTR_AUTO, CONF_GATEWAY_ID, DEVICES, DOMAIN, KEY_API


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


def _from_percentage(percentage: int) -> int:
    """Convert percent to a value that the Tradfri API understands."""
    if percentage < 20:
        # The device cannot be set to speed 5 (10%), so we should turn off the device
        # for any value below 20
        return 0

    nearest_10: int = round(percentage / 10) * 10  # Round to nearest multiple of 10
    return round(nearest_10 / 100 * 50)


def _from_fan_speed(fan_speed: int) -> int:
    """Convert the Tradfri API fan speed to a percentage value."""
    nearest_10: int = round(fan_speed / 10) * 10  # Round to nearest multiple of 10
    return round(nearest_10 / 50 * 100)


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
        10 = Min
        15
        20
        25
        30
        35
        40
        45
        50 = Max
        """
        return 10

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if not self._device_data:
            return False
        return cast(bool, self._device_data.mode)

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

        if self._device_data.mode == ATTR_AUTO:
            return ATTR_AUTO

        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if not self._device_control:
            return

        if not preset_mode == ATTR_AUTO:
            raise ValueError("Preset must be 'Auto'.")
        await self._api(self._device_control.set_mode(1))

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if not self._device_control:
            return

        if percentage is not None:
            await self._api(self._device_control.set_mode(_from_percentage(percentage)))
            return

        if preset_mode:
            await self.async_set_preset_mode(preset_mode)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if not self._device_control:
            return

        await self._api(self._device_control.set_mode(_from_percentage(percentage)))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        if not self._device_control:
            return
        await self._api(self._device_control.set_mode(0))

    def _refresh(self, device: Command, write_ha: bool = True) -> None:
        """Refresh the purifier data."""
        # Caching of air purifier control and purifier object
        self._device_control = device.air_purifier_control
        self._device_data = device.air_purifier_control.air_purifiers[0]
        super()._refresh(device, write_ha=write_ha)
