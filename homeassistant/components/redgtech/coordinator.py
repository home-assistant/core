"""Coordinator for Redgtech integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from redgtech_api.api import RedgtechAPI, RedgtechAuthError, RedgtechConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .device import RedgtechDevice

UPDATE_INTERVAL = timedelta(seconds=15)
_LOGGER = logging.getLogger(__name__)


type RedgtechConfigEntry = ConfigEntry[RedgtechDataUpdateCoordinator]


class RedgtechDataUpdateCoordinator(DataUpdateCoordinator[list[RedgtechDevice]]):
    """Coordinator to manage fetching data from the Redgtech API."""

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
            raise ConfigEntryError("Connection error during login") from e
        else:
            _LOGGER.debug("Access token obtained successfully")
            return self.access_token

    async def renew_token(self, email: str, password: str) -> None:
        """Renew the access token."""
        self.access_token = await self.api.login(email, password)
        _LOGGER.debug("Access token renewed successfully")

    async def ensure_token(self) -> None:
        """Ensure we have a valid access token, renewing if necessary."""
        if not self.access_token:
            _LOGGER.debug("No access token, logging in")
            self.access_token = await self.login(self.email, self.password)
        else:
            _LOGGER.debug("Using existing access token")

    async def _async_update_data(self) -> list[RedgtechDevice]:
        """Fetch data from the API on demand."""
        _LOGGER.debug("Fetching data from Redgtech API on demand")
        try:
            await self.ensure_token()

            data = await self.api.get_data(self.access_token)
        except RedgtechAuthError:
            _LOGGER.debug("Auth failed, trying to renew token")
            try:
                await self.renew_token(
                    self.config_entry.data[CONF_EMAIL],
                    self.config_entry.data[CONF_PASSWORD],
                )
                data = await self.api.get_data(self.access_token)
            except RedgtechAuthError as e:
                raise UpdateFailed("Authentication failed") from e
            except RedgtechConnectionError as e:
                raise UpdateFailed("Connection error during token renewal") from e

        except RedgtechConnectionError as e:
            raise UpdateFailed("Failed to connect to Redgtech API") from e

        devices: list[RedgtechDevice] = []

        for item in data["boards"]:
            display_categories = item["displayCategories"]
            device_type = display_categories[0].lower()

            device = RedgtechDevice(
                {
                    "endpointId": item["endpointId"],
                    "friendlyName": item["friendlyName"],
                    "value": item["value"],
                    "type": device_type,
                }
            )
            _LOGGER.debug("Processing device: %s", device)
            devices.append(device)

        return devices
