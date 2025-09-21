"""Coordinator to handle keeping device states up to date."""

from __future__ import annotations

from datetime import timedelta
import logging
import time

from pycync import Cync, CyncDevice, User
from pycync.exceptions import AuthFailedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_EXPIRES_AT, CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)

type CyncConfigEntry = ConfigEntry[CyncCoordinator]


class CyncCoordinator(DataUpdateCoordinator[dict[int, CyncDevice]]):
    """Coordinator to handle updating Cync device states."""

    def __init__(
        self, hass: HomeAssistant, config_entry: CyncConfigEntry, cync: Cync
    ) -> None:
        """Initialize the Cync coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Cync Data Coordinator",
            config_entry=config_entry,
            update_interval=timedelta(seconds=30),
            always_update=True,
        )
        self.cync = cync

    async def on_data_update(self, data: dict[int, CyncDevice]) -> None:
        """Update registered devices with new data."""
        merged_data = self.data | data if self.data else data
        self.async_set_updated_data(merged_data)

    async def _async_setup(self) -> None:
        """Set up the coordinator with initial device states."""
        logged_in_user = self.cync.get_logged_in_user()
        if (
            self.config_entry
            and logged_in_user.access_token != self.config_entry.data[CONF_ACCESS_TOKEN]
        ):
            await self._update_config_cync_credentials(logged_in_user)

    async def _async_update_data(self) -> dict[int, CyncDevice]:
        """First, refresh the user's auth token if it is set to expire in less than one hour.

        Then, fetch all current device states.
        """

        logged_in_user = self.cync.get_logged_in_user()
        if logged_in_user.expires_at - time.time() < 3600:
            await self._async_refresh_cync_credentials()

        self.cync.update_device_states()
        current_device_states = self.cync.get_devices()

        return {device.device_id: device for device in current_device_states}

    async def _async_refresh_cync_credentials(self) -> None:
        """Attempt to refresh the Cync user's authentication token."""

        try:
            refreshed_user = await self.cync.refresh_credentials()
        except AuthFailedError as ex:
            raise ConfigEntryAuthFailed("Unable to refresh user token") from ex
        else:
            await self._update_config_cync_credentials(refreshed_user)

    async def _update_config_cync_credentials(self, user_info: User) -> None:
        """Update the config entry with current user info."""

        if self.config_entry:
            new_data = {**self.config_entry.data}
            new_data[CONF_ACCESS_TOKEN] = user_info.access_token
            new_data[CONF_REFRESH_TOKEN] = user_info.refresh_token
            new_data[CONF_EXPIRES_AT] = user_info.expires_at
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
