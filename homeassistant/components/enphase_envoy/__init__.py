"""The Enphase Envoy integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from envoy_reader.envoy_reader import EnvoyReader
import httpx

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COORDINATOR,
    DATA_LISTENER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NAME,
    PLATFORMS,
    SENSORS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enphase Envoy from a config entry."""
    config = entry.data
    name = config[CONF_NAME]

    envoy_reader = EnvoyReader(
        config[CONF_HOST],
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        inverters=True,
        async_client=get_async_client(hass),
    )

    scan_interval = entry.options[CONF_SCAN_INTERVAL] or DEFAULT_SCAN_INTERVAL

    async def async_update_data():
        """Fetch data from API endpoint."""
        data = {}
        async with async_timeout.timeout(30):
            try:
                await envoy_reader.getData()
            except httpx.HTTPStatusError as err:
                raise ConfigEntryAuthFailed from err
            except httpx.HTTPError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

            for description in SENSORS:
                if description.key != "inverters":
                    data[description.key] = await getattr(
                        envoy_reader, description.key
                    )()
                else:
                    data[
                        "inverters_production"
                    ] = await envoy_reader.inverters_production()

            _LOGGER.debug("Retrieved data from API: %s", data)

            return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"envoy {name}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        envoy_reader.get_inverters = False
        await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        NAME: name,
        DATA_LISTENER: [entry.add_update_listener(update_listener)],
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    for listener in hass.data[DOMAIN][entry.entry_id][DATA_LISTENER]:
        listener()
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_listener(hass, config_entry):
    """Update when config_entry options update."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    old_update_interval = coordinator.update_interval
    coordinator.update_interval = timedelta(
        seconds=config_entry.options.get(CONF_SCAN_INTERVAL)
    )
    if old_update_interval != coordinator.update_interval:
        _LOGGER.debug(
            "Changing scan_interval from %s to %s",
            old_update_interval,
            coordinator.update_interval,
        )
