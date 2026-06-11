"""The Aqvify integration."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import AqvifyConfigEntry, AqvifyCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AqvifyConfigEntry) -> bool:
    """Set up Aqvify from a config entry."""

    coordinator = AqvifyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AqvifyConfigEntry) -> bool:
    """Unload Aqvify config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: AqvifyConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from an Aqvify device."""

    return not device_entry.identifiers.intersection(
        (DOMAIN, f"{config_entry.unique_id}_{device_id}")
        for device_id in config_entry.runtime_data.data.devices.devices
    )
