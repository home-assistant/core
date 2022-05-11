"""Coordinator for BMW."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from bimmer_connected.account import MyBMWAccount
from bimmer_connected.api.regions import get_region_from_name
from bimmer_connected.vehicle.models import GPSPosition

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_READ_ONLY, CONF_REFRESH_TOKEN, DOMAIN

SCAN_INTERVAL = timedelta(seconds=300)
_LOGGER = logging.getLogger(__name__)


class BMWDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching BMW data."""

    account: MyBMWAccount

    def __init__(self, hass: HomeAssistant, *, entry: ConfigEntry) -> None:
        """Initialize account-wide BMW data updater."""
        self.account = MyBMWAccount(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            get_region_from_name(entry.data[CONF_REGION]),
            observer_position=GPSPosition(hass.config.latitude, hass.config.longitude),
        )
        self.read_only = entry.options[CONF_READ_ONLY]
        self._entry = entry

        if CONF_REFRESH_TOKEN in entry.data:
            self.account.set_refresh_token(entry.data[CONF_REFRESH_TOKEN])

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry.data['username']}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from BMW."""
        try:
            old_refresh_token = self.account.refresh_token
            async with async_timeout.timeout(15):
                await self.account.get_vehicles()
            if self.account.refresh_token != old_refresh_token:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={
                        **self._entry.data,
                        CONF_REFRESH_TOKEN: self.account.refresh_token,
                    },
                )
        except OSError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def notify_listeners(self) -> None:
        """Notify all listeners to refresh HA state machine."""
        for update_callback in self._listeners:
            update_callback()
