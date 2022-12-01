"""Support for testing internet speed via Speedtest.net."""
from __future__ import annotations

from datetime import timedelta
from functools import partial

import speedtest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_STARTED,
    Platform,
)
from homeassistant.core import CoreState, Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_MANUAL, DEFAULT_SCAN_INTERVAL, DOMAIN
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

    async def _enable_scheduled_speedtests(event: Event | None = None) -> None:
        """Activate the data update coordinator."""
        coordinator.update_interval = timedelta(
            minutes=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        await coordinator.async_refresh()

    if not config_entry.options.get(CONF_MANUAL, False):
        if hass.state == CoreState.running:
            await _enable_scheduled_speedtests()
        else:
            # Running a speed test during startup can prevent
            # integrations from being able to setup because it
            # can saturate the network interface.
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, _enable_scheduled_speedtests
            )

    hass.data[DOMAIN] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(
        config_entry.add_update_listener(options_updated_listener)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload SpeedTest Entry from config_entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data.pop(DOMAIN)
    return unload_ok


async def options_updated_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator: SpeedTestDataCoordinator = hass.data[DOMAIN]
    if entry.options[CONF_MANUAL]:
        coordinator.update_interval = None
        return

    coordinator.update_interval = timedelta(minutes=entry.options[CONF_SCAN_INTERVAL])
    await coordinator.async_request_refresh()
