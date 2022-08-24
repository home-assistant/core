"""Inels switch entity."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import COORDINATOR_LIST, DOMAIN, ICON_SWITCH
from .coordinator import InelsDeviceUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Inels switch.."""
    coordinator_data = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR_LIST]

    async_add_entities(
        [
            InelsSwitch(device_coordinator)
            for device_coordinator in coordinator_data
            if device_coordinator.device.device_type == Platform.SWITCH
        ],
    )


class InelsSwitch(InelsBaseEntity, SwitchEntity):
    """The platform class required by Home Assistant."""

    def __init__(self, device_coordinator: InelsDeviceUpdateCoordinator) -> None:
        """Initialize a switch."""
        super().__init__(device_coordinator=device_coordinator)
        self._device_control = self._device

    def _refresh(self) -> None:
        """Refresh the device."""
        super()._refresh()
        self._device_control = self._device

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._device_control.state

    @property
    def icon(self) -> str | None:
        """Switch icon."""
        return ICON_SWITCH

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        if not self._device_control.is_available:
            return None
        await self.hass.async_add_executor_job(self._device_control.set_ha_value, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        if not self._device_control.is_available:
            return None
        await self.hass.async_add_executor_job(self._device_control.set_ha_value, True)
