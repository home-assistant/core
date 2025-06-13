"""Coordinator for Redgtech integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from dataclasses import dataclass
from typing import TYPE_CHECKING
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_OFF, CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import HomeAssistantError, ConfigEntryError, ConfigEntryNotReady
from redgtech_api.api import RedgtechAPI, RedgtechAuthError, RedgtechConnectionError
from .const import DOMAIN

UPDATE_INTERVAL = timedelta(minutes=1)
_LOGGER = logging.getLogger(__name__)

@dataclass
class RedgtechDevice:
    """Representation of a Redgtech device."""
    unique_id: str
    name: str
    state: str


type RedgtechConfigEntry = ConfigEntry[RedgtechDataUpdateCoordinator]


class RedgtechDataUpdateCoordinator(DataUpdateCoordinator[list[RedgtechDevice]]):
    """Coordinator to manage fetching data from the Redgtech API."""

    config_entry: RedgtechConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: RedgtechConfigEntry):
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

    async def login(self, email: str, password: str) -> None:
        """Login to the Redgtech API and store the access token."""
        try:
            self.access_token = await self.api.login(email, password)
        except RedgtechAuthError as e:
            raise ConfigEntryError("Authentication error during login") from e
        except RedgtechConnectionError as e:
            raise ConfigEntryError("Connection error during login") from e
        _LOGGER.debug("Access token obtained successfully")

    async def renew_token(self, email: str, password: str) -> None:
        """Renew the access token."""
        self.access_token = await self.api.login(email, password)
        _LOGGER.debug("Access token renewed successfully")

    async def _async_update_data(self) -> list[RedgtechDevice]:
        """Fetch data from the API on demand."""
        _LOGGER.debug("Fetching data from Redgtech API on demand")
        try:
            if not self.access_token:
                self.access_token = await self.api.login(self.email, self.password)

            data = await self.api.get_data(self.access_token)
        except RedgtechAuthError:
            _LOGGER.debug("Auth failed, trying to renew token")
            try:
                await self.renew_token(
                    self.config_entry.data[CONF_EMAIL],
                    self.config_entry.data[CONF_PASSWORD]
                )
                data = await self.api.get_data(self.access_token)
            except RedgtechAuthError as e:
                raise ConfigEntryError("Authentication error while renewing access token") from e
            except RedgtechConnectionError as e:
                raise UpdateFailed("Connection error during token renewal") from e

        except RedgtechConnectionError as e:
            raise UpdateFailed("Failed to connect to Redgtech API") from e

        devices: list[RedgtechDevice] = []

        for item in data["boards"]:
            device = RedgtechDevice(
                unique_id=item['endpointId'],
                name=item["friendlyName"],
                state=STATE_ON if item["value"] else STATE_OFF
            )
            _LOGGER.debug("Processing device: %s", device)
            devices.append(device)

        return devices
