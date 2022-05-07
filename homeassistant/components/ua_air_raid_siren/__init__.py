"""The openweathermap component."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp
from aiohttp import ClientSession
from ukrainealarm.client import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ALERT_TYPE_AIR,
    ALERT_TYPE_ARTILLERY,
    ALERT_TYPE_UNKNOWN,
    ALERT_TYPE_URBAN_FIGHTS,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenWeatherMap as config entry."""
    api_key = entry.data[CONF_API_KEY]
    region_id = entry.data.get(CONF_REGION)

    websession = async_get_clientsession(hass)

    coordinator = UAAirRaidSirenDataUpdateCoordinator(
        hass, websession, api_key, region_id
    )
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class UAAirRaidSirenDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching AccuWeather data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        api_key,
        region_id,
    ) -> None:
        """Initialize."""
        self.region_id = region_id
        self.ukrainealarm = Client(session, api_key)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            res = await self.ukrainealarm.get_alerts(self.region_id)
        except aiohttp.ClientError as error:
            raise UpdateFailed(f"Error fetching status from API: {error}") from error

        current = {
            ALERT_TYPE_AIR: False,
            ALERT_TYPE_UNKNOWN: False,
            ALERT_TYPE_ARTILLERY: False,
            ALERT_TYPE_URBAN_FIGHTS: False,
        }
        for alert in res[0]["activeAlerts"]:
            if alert["type"] == ALERT_TYPE_AIR:
                current[ALERT_TYPE_AIR] = True
            if alert["type"] == ALERT_TYPE_UNKNOWN:
                current[ALERT_TYPE_UNKNOWN] = True
            if alert["type"] == ALERT_TYPE_ARTILLERY:
                current[ALERT_TYPE_ARTILLERY] = True
            if alert["type"] == ALERT_TYPE_URBAN_FIGHTS:
                current[ALERT_TYPE_URBAN_FIGHTS] = True

        return current
