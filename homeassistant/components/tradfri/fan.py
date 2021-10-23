"""Represent an air purifier."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from pytradfri.command import Command

from homeassistant.components.fan import SUPPORT_PRESET_MODE, FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import TradfriBaseDevice
from .const import CONF_GATEWAY_ID, DEVICES, DOMAIN, KEY_API


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

    purifiers = [dev for dev in devices if dev.has_air_purifier_control]
    if purifiers:
        async_add_entities(
            TradfriAirPurifierFan(purifier, api, gateway_id) for purifier in purifiers
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

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_PRESET_MODE

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return 11

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if not self._device_data:
            return False
        return cast(bool, self._device_data.mode)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        return ["0", "1", "10", "15", "20", "25", "30", "35", "40", "45", "50"]

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if not self._device_data:
            return None
        return str(self._device_data.mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if not self._device_control:
            return
        await self._api(self._device_control.set_mode(int(preset_mode)))

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan in the auto mode."""
        if not self._device_control:
            return
        await self._api(self._device_control.set_mode(1))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        if not self._device_control:
            return
        await self._api(self._device_control.set_mode(0))

    def _refresh(self, device: Command) -> None:
        """Refresh the purifier data."""
        super()._refresh(device)

        # Caching of air purifier control and purifier object
        self._device_control = device.air_purifier_control
        self._device_data = device.air_purifier_control.air_purifiers[0]
