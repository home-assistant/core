"""Platform for Lunatone light integration."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LunatoneConfigEntry, LunatoneDevicesDataUpdateCoordinator

PARALLEL_UPDATES = 0
STATUS_UPDATE_DELAY = 0.04


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lunatone Light platform."""
    coordinator_info = config_entry.runtime_data.coordinator_info
    coordinator_devices = config_entry.runtime_data.coordinator_devices

    async_add_entities(
        [
            LunatoneLight(
                coordinator_devices, device.id, coordinator_info.data.device.serial
            )
            for device in coordinator_devices.data.devices
        ]
    )


class LunatoneLight(
    CoordinatorEntity[LunatoneDevicesDataUpdateCoordinator], LightEntity
):
    """Representation of a Lunatone light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: LunatoneDevicesDataUpdateCoordinator,
        device_id: int,
        interface_serial_number: int,
    ) -> None:
        """Initialize a LunatoneLight."""
        super().__init__(coordinator=coordinator)
        self._device_id = device_id
        self._interface_serial_number = interface_serial_number
        self._device = self.coordinator.device_mapping.get(self._device_id)
        self._attr_unique_id = f"{interface_serial_number}-device{device_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        assert self.unique_id
        name = self._device.name if self._device is not None else None
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=name,
            via_device=(DOMAIN, str(self._interface_serial_number)),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._device is not None

    @property
    def is_on(self) -> bool:
        """Return True if light is on."""
        return self._device.is_on if self._device is not None else False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._device = self.coordinator.device_mapping.get(self._device_id)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if self._device is None:
            return
        await self._device.switch_on()
        await asyncio.sleep(STATUS_UPDATE_DELAY)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        if self._device is None:
            return
        await self._device.switch_off()
        await asyncio.sleep(STATUS_UPDATE_DELAY)
        await self.coordinator.async_refresh()
