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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ALERT_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=10)


class UkraineAlarmDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Ukraine Alarm API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        session: ClientSession,
    ) -> None:
        """Initialize."""
        self.region_id = config_entry.data[CONF_REGION]
        self.uasiren = Client(session)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            res = await self.uasiren.get_alerts(self.region_id)
        except aiohttp.ClientError as error:
            raise UpdateFailed(f"Error fetching alerts from API: {error}") from error

        current = dict.fromkeys(ALERT_TYPES, False)
        for alert in res[0]["activeAlerts"]:
            current[alert["type"]] = True

        return current
