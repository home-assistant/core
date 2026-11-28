"""Expose the direct Wi-Fi switch in Home Assistant."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeimanConfigEntry, HeimanCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeimanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the switch entity for this config entry."""
    async_add_entities([HeimanSwitch(entry.runtime_data)])


class HeimanSwitch(CoordinatorEntity[HeimanCoordinator], SwitchEntity):
    """The primary power control for the device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: HeimanCoordinator) -> None:
        """Initialize the registered switch."""
        super().__init__(coordinator)
        info = coordinator.info
        self._attr_unique_id = info.mac
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.mac)},
            connections={(CONNECTION_NETWORK_MAC, info.mac)},
            manufacturer="Heiman",
            name=info.name,
            model=info.model,
            sw_version=info.firmware,
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return the state reported by the switch."""
        return self.coordinator.data

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.async_set_power(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.async_set_power(False)
