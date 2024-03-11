"""Support for testing internet speed via Speedtest.net."""

from __future__ import annotations

from functools import partial

import speedtest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN
from .coordinator import SpeedTestDataCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Speedtest.net component."""
    try:
        api = await hass.async_add_executor_job(
            partial(speedtest.Speedtest, secure=True)
        )
        coordinator = SpeedTestDataCoordinator(hass, config_entry, api)
        await hass.async_add_executor_job(coordinator.update_servers)
    except speedtest.SpeedtestException as err:
        raise ConfigEntryNotReady from err

    async def _async_finish_startup(hass: HomeAssistant) -> None:
        """Run this only when HA has finished its startup."""
        await coordinator.async_config_entry_first_refresh()

    # Don't start a speedtest during startup
    async_at_started(hass, _async_finish_startup)

    hass.data[DOMAIN] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload SpeedTest Entry from config_entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data.pop(DOMAIN)
    return unload_ok
