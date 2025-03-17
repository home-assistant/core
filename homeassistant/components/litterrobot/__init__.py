"""The Litter-Robot integration."""

from __future__ import annotations

import itertools

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.UPDATE,
    Platform.VACUUM,
]


async def async_setup_entry(hass: HomeAssistant, entry: LitterRobotConfigEntry) -> bool:
    """Set up Litter-Robot from a config entry."""
    coordinator = LitterRobotDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LitterRobotConfigEntry
) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.account.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: LitterRobotConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        for _id in itertools.chain(
            (robot.serial for robot in entry.runtime_data.account.robots),
            (pet.id for pet in entry.runtime_data.account.pets),
        )
        if _id == identifier[1]
    )
