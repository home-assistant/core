"""Files to interact with a the ESPHome dashboard."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

import aiohttp
from esphome_dashboard_api import ConfiguredDevice, ESPHomeDashboardAPI

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    pass

KEY_DASHBOARD = "esphome_dashboard"


@callback
def async_get_dashboard(hass: HomeAssistant) -> ESPHomeDashboard | None:
    """Get an instance of the dashboard if set."""
    return hass.data.get(KEY_DASHBOARD)


def async_set_dashboard_info(
    hass: HomeAssistant, addon_slug: str, host: str, port: int
) -> None:
    """Set the dashboard info."""
    hass.data[KEY_DASHBOARD] = ESPHomeDashboard(
        hass,
        addon_slug,
        f"http://{host}:{port}",
        async_get_clientsession(hass),
    )


class ESPHomeDashboard(DataUpdateCoordinator[dict[str, ConfiguredDevice]]):
    """Class to interact with the ESPHome dashboard."""

    _first_fetch_lock: asyncio.Lock | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        addon_slug: str,
        url: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name="ESPHome Dashboard",
            update_interval=timedelta(minutes=5),
        )
        self.addon_slug = addon_slug
        self.api = ESPHomeDashboardAPI(url, session)

    async def _async_update_data(self) -> dict:
        """Fetch device data."""
        devices = await self.api.get_devices()
        return {dev["name"]: dev for dev in devices["configured"]}
