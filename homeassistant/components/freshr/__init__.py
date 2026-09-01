"""The Fresh-r integration."""

import asyncio

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .coordinator import (
    FreshrConfigEntry,
    FreshrData,
    FreshrDevicesCoordinator,
    FreshrReadingsCoordinator,
)

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: FreshrConfigEntry) -> bool:
    """Set up Fresh-r from a config entry."""
    devices_coordinator = FreshrDevicesCoordinator(hass, entry)
    await devices_coordinator.async_config_entry_first_refresh()

    readings: dict[str, FreshrReadingsCoordinator] = {
        device_id: FreshrReadingsCoordinator(
            hass, entry, device, devices_coordinator.client
        )
        for device_id, device in devices_coordinator.data.items()
    }
    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in readings.values()
        )
    )

    entry.runtime_data = FreshrData(
        devices=devices_coordinator,
        readings=readings,
    )

    known_devices: set[str] = set(readings)

    @callback
    def _handle_coordinator_update() -> None:
        current = set(devices_coordinator.data)
        removed_ids = known_devices - current
        if removed_ids:
            known_devices.difference_update(removed_ids)
            for device_id in removed_ids:
                entry.runtime_data.readings.pop(device_id, None)
        new_ids = current - known_devices
        if not new_ids:
            return
        known_devices.update(new_ids)
        for device_id in new_ids:
            device = devices_coordinator.data[device_id]
            readings_coordinator = FreshrReadingsCoordinator(
                hass, entry, device, devices_coordinator.client
            )
            entry.runtime_data.readings[device_id] = readings_coordinator
            hass.async_create_task(
                readings_coordinator.async_refresh(),
                name=f"freshr_readings_refresh_{device_id}",
            )

    entry.async_on_unload(
        devices_coordinator.async_add_listener(_handle_coordinator_update)
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreshrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
