"""Coordinator for Redgtech integration."""

import logging
import aiohttp
from datetime import timedelta
from dataclasses import dataclass
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_OFF, CONF_ACCESS_TOKEN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import HomeAssistantError, ConfigEntryError
from redgtech_api.api import RedgtechAPI, RedgtechAuthError, RedgtechConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_LOGGER.debug("Coordinator for Redgtech is being initialized.")

@dataclass
class RedgtechDevice:
    """Representation of a Redgtech device."""
    id: str
    name: str
    state: str

class RedgtechConfigEntry(ConfigEntry):
    """Custom ConfigEntry for Redgtech integration."""

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
            update_method=self.fetch_data,
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
            _LOGGER.error("Unexpected error during login: %s", e)
            raise ConfigEntryError("Unexpected error during login") from e

    async def fetch_data(self) -> list[RedgtechDevice]:
        """Fetch data from the API on demand."""
        _LOGGER.debug("Fetching data from Redgtech API on demand")
        try:
            data = await self.api.get_data(self.access_token)
        except RedgtechAuthError:
            _LOGGER.warning("Access token expired, attempting to renew")
            await self.renew_token(self.config_entry.data["email"], self.config_entry.data["password"])
            data = await self.api.get_data(self.access_token)
        except RedgtechConnectionError as e:
            _LOGGER.error("Connection error while fetching data: %s", e)
            raise UpdateFailed("Failed to connect to Redgtech API") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while fetching data: %s", e)
            raise UpdateFailed("Unexpected error while fetching data") from e

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

    async def set_device_state(self, device_id: str, state: bool) -> None:
        """Set the state of a device."""
        _LOGGER.debug("Setting device state: %s to %s", device_id, state)
        try:
            await self.api.set_switch_state(device_id, state, self.access_token)
        except RedgtechAuthError:
            _LOGGER.warning("Access token expired, attempting to renew")
            await self.renew_token(self.config_entry.data["email"], self.config_entry.data["password"])
            await self.api.set_switch_state(device_id, state, self.access_token)
        except RedgtechConnectionError as e:
            _LOGGER.error("Connection error while setting device state: %s", e)
            raise ConfigEntryError("Failed to set device state") from e
        except Exception as e:
            _LOGGER.error("Unexpected error setting device state: %s", e)
            raise HomeAssistantError("Unexpected error setting device state") from e
        _LOGGER.debug("Device state set successfully")
        await self._async_update_data()
        _LOGGER.debug("Device state updated and data refreshed")

    async def renew_token(self, email: str, password: str) -> None:
        """Renew the access token."""
        _LOGGER.debug("Renewing access token")
        try:
            new_access_token = await self.api.login(email, password)
            self.access_token = new_access_token
            _LOGGER.debug("Access token renewed successfully")
        except Exception as e:
            _LOGGER.error("Failed to renew access token: %s", e)
            raise ConfigEntryError("Failed to renew access token") from e