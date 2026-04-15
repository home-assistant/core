"""Coordinator for Redgtech integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from redgtech_api.api import RedgtechAPI, RedgtechAuthError, RedgtechConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

UPDATE_INTERVAL = timedelta(seconds=15)
_LOGGER = logging.getLogger(__name__)


@dataclass
class RedgtechDevice:
    """Representation of a Redgtech device."""

    unique_id: str
    name: str
    state: bool


type RedgtechConfigEntry = ConfigEntry[RedgtechDataUpdateCoordinator]


class RedgtechDataUpdateCoordinator(DataUpdateCoordinator[dict[str, RedgtechDevice]]):
    """Coordinator to manage fetching data from the Redgtech API.

    Uses a dictionary keyed by unique_id for O(1) device lookup instead of O(n) list iteration.
    """

    config_entry: RedgtechConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: RedgtechConfigEntry) -> None:
        """Initialize the coordinator."""
        self.api = RedgtechAPI()
        self.access_token: str | None = None
        self.email = config_entry.data[CONF_EMAIL]
        self.password = config_entry.data[CONF_PASSWORD]

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )

    async def login(self, email: str, password: str) -> str | None:
        """Login to the Redgtech API and return the access token."""
        try:
            self.access_token = await self.api.login(email, password)
        except RedgtechAuthError as e:
            raise ConfigEntryError("Authentication error during login") from e
        except RedgtechConnectionError as e:
            raise UpdateFailed("Connection error during login") from e
        else:
            _LOGGER.debug("Access token obtained successfully")
            return self.access_token

    async def renew_token(self, email: str, password: str) -> None:
        """Renew the access token."""
        self.access_token = await self.api.login(email, password)
        _LOGGER.debug("Access token renewed successfully")

    async def call_api_with_valid_token[_R, *_Ts](
        self, api_call: Callable[[*_Ts], Coroutine[Any, Any, _R]], *args: *_Ts
    ) -> _R:
        """Make an API call with a valid token.

        Ensure we have a valid access token, renewing it if necessary.
        """
        if not self.access_token:
            _LOGGER.debug("No access token, logging in")
            self.access_token = await self.login(self.email, self.password)
        else:
            _LOGGER.debug("Using existing access token")
        try:
            return await api_call(*args)
        except RedgtechAuthError:
            _LOGGER.debug("Auth failed, trying to renew token")
            await self.renew_token(
                self.config_entry.data[CONF_EMAIL],
                self.config_entry.data[CONF_PASSWORD],
            )
            return await api_call(*args)

    async def _async_update_data(self) -> dict[str, RedgtechDevice]:
        """Fetch data from the API on demand.

        Returns a dictionary keyed by unique_id for efficient device lookup.
        """
        _LOGGER.debug("Fetching data from Redgtech API on demand")
        try:
            data = await self.call_api_with_valid_token(
                self.api.get_data, self.access_token
            )
        except RedgtechAuthError as e:
            raise ConfigEntryError("Authentication failed") from e
        except RedgtechConnectionError as e:
            raise UpdateFailed("Failed to connect to Redgtech API") from e

        devices: dict[str, RedgtechDevice] = {}

        for item in data["boards"]:
            display_categories = {cat.lower() for cat in item["displayCategories"]}

            if "light" in display_categories or "switch" not in display_categories:
                continue

            device = RedgtechDevice(
                unique_id=item["endpointId"],
                name=item["friendlyName"],
                state=item["value"],
            )
            _LOGGER.debug("Processing device: %s", device)
            devices[device.unique_id] = device

        return devices
