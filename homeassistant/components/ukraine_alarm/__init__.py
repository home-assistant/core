"""The ukraine_alarm component."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp
from aiohttp import ClientSession
from uasiren.client import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ALERT_TYPES, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ukraine Alarm as config entry."""
    region_id = entry.data[CONF_REGION]

    websession = async_get_clientsession(hass)

    coordinator = UkraineAlarmDataUpdateCoordinator(hass, websession, region_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class UkraineAlarmDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):  # pylint: disable=hass-enforce-coordinator-module
    """Class to manage fetching Ukraine Alarm API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        region_id: str,
    ) -> None:
        """Initialize."""
        self.region_id = region_id
        self.uasiren = Client(session)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            res = await self.uasiren.get_alerts(self.region_id)
        except aiohttp.ClientError as error:
            raise UpdateFailed(f"Error fetching alerts from API: {error}") from error

        current = {alert_type: False for alert_type in ALERT_TYPES}
        for alert in res[0]["activeAlerts"]:
            current[alert["type"]] = True

        return current
