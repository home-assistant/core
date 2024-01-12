"""Support for testing internet speed via Speedtest.net."""
from __future__ import annotations

from functools import partial

import speedtest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

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

    async def _request_refresh(event: Event) -> None:
        """Request a refresh."""
        await coordinator.async_request_refresh()

    if hass.state is CoreState.running:
        await coordinator.async_config_entry_first_refresh()
    else:
        # Running a speed test during startup can prevent
        # integrations from being able to setup because it
        # can saturate the network interface.
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _request_refresh)

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
