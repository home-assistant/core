"""Coordinator for Redgtech integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from dataclasses import dataclass
from typing import TYPE_CHECKING
from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_ON, STATE_OFF, CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import HomeAssistantError, ConfigEntryError
from redgtech_api.api import RedgtechAPI, RedgtechAuthError, RedgtechConnectionError
from .const import DOMAIN

if TYPE_CHECKING:
    from . import RedgtechConfigEntry

_LOGGER = logging.getLogger(__name__)
_LOGGER.debug("Coordinator for Redgtech is being initialized.")

@dataclass
class RedgtechDevice:
    """Representation of a Redgtech device."""
    id: str
    name: str
    state: str

class RedgtechDataUpdateCoordinator(DataUpdateCoordinator[list[RedgtechDevice]]):
    """Coordinator to manage fetching data from the Redgtech API."""

    config_entry: RedgtechConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: RedgtechConfigEntry):
        """Initialize the coordinator."""
        self.api = RedgtechAPI()
        self.access_token = config_entry.data[CONF_ACCESS_TOKEN]

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
            config_entry=config_entry,
        )

    async def login(self, email: str, password: str) -> str:
        """Login to the Redgtech API and return the access token."""
        try:
            access_token = await self.api.login(email, password)
            self.access_token = access_token
            return access_token
        except Exception as e:
            raise ConfigEntryError("Unexpected error during login") from e

    async def _async_update_data(self) -> list[RedgtechDevice]:
        """Fetch data from the API on demand."""
        _LOGGER.debug("Fetching data from Redgtech API on demand")
        try:
            data = await self.api.get_data(self.access_token)
        except RedgtechAuthError:
            await self.renew_token(self.config_entry.data[CONF_EMAIL], self.config_entry.data[CONF_PASSWORD])
            data = await self.api.get_data(self.access_token)
        except RedgtechConnectionError as e:
            raise UpdateFailed("Failed to connect to Redgtech API") from e
        except HomeAssistantError as e:
            raise UpdateFailed("Home Assistant-specific error while fetching data") from e

        devices: list[RedgtechDevice] = []

        for item in data["boards"]:
            device = RedgtechDevice(
                id=item['endpointId'],
                name=item["friendlyName"],
                state=STATE_ON if item["value"] else STATE_OFF
            )
            _LOGGER.debug("Processing device: %s", device)
            devices.append(device)

        return devices

    async def renew_token(self) -> None:
        """Renew the access token."""
        _LOGGER.debug("Renewing access token")
        try:
            new_access_token = await self.api.login(
                self.config_entry.data[CONF_EMAIL], 
                self.config_entry.data[CONF_PASSWORD]
            )
            self.access_token = new_access_token
            _LOGGER.debug("Access token renewed successfully")
        except RedgtechAuthError as e:
            raise ConfigEntryError("Authentication error while renewing access token") from e
        except RedgtechConnectionError as e:
            raise ConfigEntryError("Connection error while renewing access token") from e
        except Exception as e:
            raise HomeAssistantError("Unexpected error while renewing access token") from e