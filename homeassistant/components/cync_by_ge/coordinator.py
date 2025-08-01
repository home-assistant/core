"""Coordinator to handle keeping device states up to date."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
import time

from pycync import Cync
from pycync.exceptions import AuthFailedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_ACCESS_TOKEN, CONF_EXPIRES_AT, CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)

type CyncConfigEntry = ConfigEntry[CyncData]


@dataclass
class CyncData:
    """Holds relevant objects for operating and managing devices."""

    api: Cync
    coordinator: CyncCoordinator


class CyncCoordinator(DataUpdateCoordinator):
    """Coordinator to handle updating Cync device states."""

    def __init__(self, hass, config_entry, cync: Cync) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Cync Data Coordinator",
            config_entry=config_entry,
            update_interval=timedelta(seconds=30),
            always_update=True,
        )
        self.hass = hass
        self.cync = cync

    def on_data_update(self, data):
        """Update registered devices with new data."""
        self.hass.add_job(self.async_set_updated_data, data)

    async def _async_setup(self):
        """Set up the coordinator.

        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        self.cync.update_device_states()

    async def _async_update_data(self):
        """First, refresh the user's auth token if it is set to expire in less than one hour.

        Then, send a request to update the device statuses.
        """

        logged_in_user = self.cync.get_logged_in_user()
        if logged_in_user.expires_at - time.time() < 3600:
            await self._async_update_cync_credentials()

        self.cync.update_device_states()

    async def _async_update_cync_credentials(self):
        """Attempt to refresh the Cync authentication token."""
        try:
            refreshed_user = await self.cync.refresh_credentials()
        except AuthFailedError as ex:
            raise ConfigEntryAuthFailed("Unable to refresh user token") from ex
        else:
            new_data = {**self.config_entry.data}
            new_data[CONF_ACCESS_TOKEN] = refreshed_user.access_token
            new_data[CONF_REFRESH_TOKEN] = refreshed_user.refresh_token
            new_data[CONF_EXPIRES_AT] = refreshed_user.expires_at
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
