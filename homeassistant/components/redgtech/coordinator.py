"""Coordinator for Redgtech integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from redgtech_api.api import RedgtechAPI, RedgtechAuthError, RedgtechConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, STATE_OFF, STATE_ON
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
    state: str


type RedgtechConfigEntry = ConfigEntry[RedgtechDataUpdateCoordinator]


class RedgtechDataUpdateCoordinator(DataUpdateCoordinator[list[RedgtechDevice]]):
    """Coordinator to manage fetching data from the Redgtech API."""

    config_entry: RedgtechConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: RedgtechConfigEntry) -> None:
        """Initialize the coordinator."""
        self.api: Any = RedgtechAPI()  # type: ignore[no-untyped-call]
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

            data = await self.api.get_data(self.access_token or "")
        except RedgtechAuthError:
            _LOGGER.debug("Auth failed, trying to renew token")
            try:
                await self.renew_token(
                    self.config_entry.data[CONF_EMAIL],
                    self.config_entry.data[CONF_PASSWORD],
                )
                data = await self.api.get_data(self.access_token or "")
            except RedgtechAuthError as e:
                # Start reauth flow instead of raising ConfigEntryError
                _LOGGER.warning("Authentication failed, starting reauth flow")
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={
                            "source": "reauth",
                            "entry_id": self.config_entry.entry_id,
                        },
                        data=self.config_entry.data,
                    )
                )
                raise UpdateFailed("Authentication failed, reauth flow started") from e
            except RedgtechConnectionError as e:
                raise UpdateFailed("Connection error during token renewal") from e

        except RedgtechConnectionError as e:
            raise UpdateFailed("Failed to connect to Redgtech API") from e

        devices: list[RedgtechDevice] = []

        for item in data["boards"]:
            device = RedgtechDevice(
                unique_id=item["endpointId"],
                name=item["friendlyName"],
                state=STATE_ON if item["value"] else STATE_OFF,
            )
            _LOGGER.debug("Processing device: %s", device)
            devices.append(device)

        return devices
