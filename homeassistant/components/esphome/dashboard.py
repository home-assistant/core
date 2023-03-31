"""Files to interact with a the ESPHome dashboard."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import aiohttp
from awesomeversion import AwesomeVersion
from esphome_dashboard_api import ConfiguredDevice, ESPHomeDashboardAPI

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

KEY_DASHBOARD = "esphome_dashboard"


@callback
def async_get_dashboard(hass: HomeAssistant) -> ESPHomeDashboard | None:
    """Get an instance of the dashboard if set."""
    return hass.data.get(KEY_DASHBOARD)


async def async_set_dashboard_info(
    hass: HomeAssistant, addon_slug: str, host: str, port: int
) -> None:
    """Set the dashboard info."""
    url = f"http://{host}:{port}"

    # Do nothing if we already have this data.
    if (
        (cur_dashboard := hass.data.get(KEY_DASHBOARD))
        and cur_dashboard.addon_slug == addon_slug
        and cur_dashboard.url == url
    ):
        return

    dashboard = ESPHomeDashboard(hass, addon_slug, url, async_get_clientsession(hass))
    try:
        await dashboard.async_request_refresh()
    except UpdateFailed as err:
        logging.getLogger(__name__).error("Ignoring dashboard info: %s", err)
        return

    hass.data[KEY_DASHBOARD] = dashboard

    reloads = [
        hass.config_entries.async_reload(entry.entry_id)
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    # Re-auth flows will check the dashboard for encryption key when the form is requested
    reauths = [
        hass.config_entries.flow.async_configure(flow["flow_id"])
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN and flow["context"]["source"] == SOURCE_REAUTH
    ]
    if reloads or reauths:
        await asyncio.gather(*reloads, *reauths)


class ESPHomeDashboard(DataUpdateCoordinator[dict[str, ConfiguredDevice]]):
    """Class to interact with the ESPHome dashboard."""

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
        self.url = url
        self.api = ESPHomeDashboardAPI(url, session)

    @property
    def supports_update(self) -> bool:
        """Return whether the dashboard supports updates."""
        if self.data is None:
            raise RuntimeError("Data needs to be loaded first")

        if len(self.data) == 0:
            return False

        esphome_version: str = next(iter(self.data.values()))["current_version"]

        # There is no January release
        return AwesomeVersion(esphome_version) > AwesomeVersion("2023.1.0")

    async def _async_update_data(self) -> dict:
        """Fetch device data."""
        devices = await self.api.get_devices()
        return {dev["name"]: dev for dev in devices["configured"]}
