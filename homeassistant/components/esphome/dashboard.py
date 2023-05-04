"""Files to interact with a the ESPHome dashboard."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import aiohttp
from awesomeversion import AwesomeVersion
from esphome_dashboard_api import ConfiguredDevice, ESPHomeDashboardAPI

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

KEY_DASHBOARD = "esphome_dashboard"

UPDATE_INTERVAL = timedelta(minutes=5)


@callback
def async_get_dashboard(hass: HomeAssistant) -> ESPHomeDashboard:
    """Get the instance of the dashboard."""
    if KEY_DASHBOARD not in hass.data:
        # We don't have a dashboard yet, create one with no addon
        # and no url. This will be updated later when the addon is
        # discovered.
        dashboard = ESPHomeDashboard(hass, None, None, async_get_clientsession(hass))
        hass.data[KEY_DASHBOARD] = dashboard
    else:
        dashboard = hass.data[KEY_DASHBOARD]
    return dashboard


async def async_set_dashboard_info(
    hass: HomeAssistant, addon_slug: str, host: str, port: int
) -> None:
    """Set the dashboard info."""
    dashboard = async_get_dashboard(hass)
    await dashboard.async_update_source(addon_slug, host, port)
    if not dashboard.last_update_success:
        return

    # Re-auth flows will check the dashboard for encryption key when the form is requested
    if reauths := [
        hass.config_entries.flow.async_configure(flow["flow_id"])
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN and flow["context"]["source"] == SOURCE_REAUTH
    ]:
        await asyncio.gather(*reauths)


class ESPHomeDashboard(DataUpdateCoordinator[dict[str, ConfiguredDevice]]):
    """Class to interact with the ESPHome dashboard."""

    def __init__(
        self,
        hass: HomeAssistant,
        addon_slug: str | None,
        url: str | None,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize."""
        interval = UPDATE_INTERVAL if addon_slug else None
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name="ESPHome Dashboard",
            update_interval=interval,
        )
        self.addon_slug = addon_slug
        self.url = url
        self.api = ESPHomeDashboardAPI(url, session)

    async def async_update_source(self, addon_slug: str, host: str, port: int) -> None:
        """Update the source."""
        if self.addon_slug != addon_slug or self.url != self.api.url:
            self.url = f"http://{host}:{port}"
            self.addon_slug = addon_slug
            self.update_interval = UPDATE_INTERVAL
            self.api = ESPHomeDashboardAPI(self.url, self.api.session)
            await self.async_request_refresh()

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
