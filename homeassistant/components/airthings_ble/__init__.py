"""The Airthings BLE integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import MAX_RETRIES_AFTER_STARTUP
from .coordinator import AirthingsBLEConfigEntry, AirthingsBLEDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: AirthingsBLEConfigEntry
) -> bool:
    """Set up Airthings BLE device from a config entry."""
    coordinator = AirthingsBLEDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Once its setup and we know we are not going to delay
    # the startup of Home Assistant, we can set the max attempts
    # to a higher value. If the first connection attempt fails,
    # Home Assistant's built-in retry logic will take over.
    coordinator.airthings.set_max_attempts(MAX_RETRIES_AFTER_STARTUP)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AirthingsBLEConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
