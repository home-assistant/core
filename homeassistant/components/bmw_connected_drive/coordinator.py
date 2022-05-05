"""Coordinator for BMW."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from bimmer_connected.account import ConnectedDriveAccount
from bimmer_connected.country_selector import get_region_from_name

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=300)
_LOGGER = logging.getLogger(__name__)


class BMWDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching BMW data."""

    account: ConnectedDriveAccount

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        username: str,
        password: str,
        region: str,
        read_only: bool = False,
    ) -> None:
        """Initialize account-wide BMW data updater."""
        # Storing username & password in coordinator is needed until a new library version
        # that does not do blocking IO on init.
        self._username = username
        self._password = password
        self._region = get_region_from_name(region)

        self.account = None
        self.read_only = read_only

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{username}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from BMW."""
        try:
            async with async_timeout.timeout(15):
                if isinstance(self.account, ConnectedDriveAccount):
                    # pylint: disable=protected-access
                    await self.hass.async_add_executor_job(self.account._get_vehicles)
                else:
                    self.account = await self.hass.async_add_executor_job(
                        ConnectedDriveAccount,
                        self._username,
                        self._password,
                        self._region,
                    )
                    self.account.set_observer_position(
                        self.hass.config.latitude, self.hass.config.longitude
                    )
        except OSError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def notify_listeners(self) -> None:
        """Notify all listeners to refresh HA state machine."""
        for update_callback in self._listeners:
            update_callback()
