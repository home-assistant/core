"""The PECO Outage Counter integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Final

from peco import BadJSONError, HttpError, OutageResults, PecoOutageApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_COUNTY, DOMAIN, LOGGER, SCAN_INTERVAL

PLATFORMS: Final = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PECO Outage Counter from a config entry."""

    websession = async_get_clientsession(hass)
    api = PecoOutageApi()
    county: str = entry.data[CONF_COUNTY]

    async def async_update_data() -> OutageResults:
        """Fetch data from API."""
        try:
            data: OutageResults = (
                await api.get_outage_totals(websession)
                if county == "TOTAL"
                else await api.get_outage_count(county, websession)
            )
        except HttpError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        except BadJSONError as err:
            raise UpdateFailed(f"Error parsing data: {err}") from err
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout fetching data: {err}") from err
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name="PECO Outage Count",
        update_method=async_update_data,
        update_interval=timedelta(minutes=SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
