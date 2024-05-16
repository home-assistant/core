"""Support for testing internet speed via Speedtest.net."""

from __future__ import annotations

from functools import partial

import speedtest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.start import async_at_started

from .coordinator import SpeedTestDataCoordinator

PLATFORMS = [Platform.SENSOR]

SpeedTestConfigEntry = ConfigEntry[SpeedTestDataCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: SpeedTestConfigEntry
) -> bool:
    """Set up the Speedtest.net component."""
    try:
        api = await hass.async_add_executor_job(
            partial(speedtest.Speedtest, secure=True)
        )
        coordinator = SpeedTestDataCoordinator(hass, config_entry, api)
    except speedtest.SpeedtestException as err:
        raise ConfigEntryNotReady from err

    config_entry.runtime_data = coordinator

    async def _async_finish_startup(hass: HomeAssistant) -> None:
        """Run this only when HA has finished its startup."""
        await coordinator.async_config_entry_first_refresh()

    # Don't start a speedtest during startup
    async_at_started(hass, _async_finish_startup)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload SpeedTest Entry from config_entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
