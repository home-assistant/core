"""DataUpdateCoordinator for the Aruba ClearPass (cppm_tracker) integration."""

from datetime import timedelta
import json
import logging
from typing import override

from clearpasspy import ClearPass
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, GRANT_TYPE

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=120)

ENDPOINT_LIMIT = 100


type CppmConfigEntry = ConfigEntry[CppmDataUpdateCoordinator]


class CppmDataUpdateCoordinator(DataUpdateCoordinator[set[str]]):
    """Fetch the online endpoints from an Aruba ClearPass server."""

    config_entry: CppmConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: CppmConfigEntry) -> None:
        """Initialize the coordinator from a config entry."""
        self.host: str = config_entry.data[CONF_HOST]
        self._credentials = {
            "server": self.host,
            "grant_type": GRANT_TYPE,
            "secret": config_entry.data[CONF_API_KEY],
            "client": config_entry.data[CONF_CLIENT_ID],
        }
        self._cppm: ClearPass | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {self.host}",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> set[str]:
        """Return the MAC addresses that are currently online."""
        return await self.hass.async_add_executor_job(self._update)

    def _update(self) -> set[str]:
        """Query ClearPass for the endpoints that are online right now."""
        cppm = self._connect()
        try:
            endpoints = cppm.get_endpoints(ENDPOINT_LIMIT)["_embedded"]["items"]
            return {
                item["mac_address"]
                for item in endpoints
                if cppm.online_status(item["mac_address"])
            }
        except (KeyError, TypeError, UnboundLocalError) as err:
            # clearpasspy swallows request failures and then reads an unset
            # local, so a dropped connection surfaces as one of these.
            raise UpdateFailed(f"Error querying ClearPass at {self.host}") from err

    def _connect(self) -> ClearPass:
        """Return an authenticated client, logging in once and caching it."""
        if self._cppm is not None:
            return self._cppm
        try:
            cppm = ClearPass(self._credentials)
        except (
            KeyError,
            requests.exceptions.RequestException,
            json.JSONDecodeError,
        ) as err:
            # ClearPass authenticates in its constructor; a rejected token
            # reads as a missing key, a bad host as a request error.
            raise UpdateFailed(f"Error connecting to ClearPass at {self.host}") from err
        if cppm.access_token is None:
            raise UpdateFailed(f"Error connecting to ClearPass at {self.host}")
        self._cppm = cppm
        return cppm
