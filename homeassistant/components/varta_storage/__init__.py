"""The VARTA Storage integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta

import async_timeout
from vartastorage import vartastorage

from homeassistant import config_entries, core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VARTA Storage from a config entry."""
    varta = vartastorage.VartaStorage(entry.data["host"], entry.data["port"])
    try:
        varta.client.connect()
    except Exception as ex:
        LOGGER.warning("Could not connect to modbus server")
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)

    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener

    async def async_update_data():
        """Fetch data and preo-process the data from API endpoint."""

        def sync_update():
            """Utilizing synchronous task as the used PyPI Package is not built with async."""
            varta = vartastorage.VartaStorage(entry.data["host"], entry.data["port"])
            # Collect all data from the device at once
            varta.get_all_data()
            return varta

        try:
            async with async_timeout.timeout(10):

                # Call synchronous task to update the sensor values
                return await hass.async_add_executor_job(sync_update)
        except Exception as failed_update:
            raise UpdateFailed("Error communicating with API") from failed_update

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=1),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(entry, "sensor")]
        )
    )

    # Remove config entry from domain.
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
