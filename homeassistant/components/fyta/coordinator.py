"""Coordinator for FYTA integration."""

from datetime import datetime, timedelta
import logging
from typing import Any

from fyta_cli.fyta_connector import FytaConnector
from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class FytaCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Fyta custom coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, fyta: FytaConnector) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="FYTA Coordinator",
            update_interval=timedelta(seconds=60),
        )
        self.fyta = fyta

    async def _async_update_data(
        self,
    ) -> dict[int, dict[str, Any]]:
        """Fetch data from API endpoint."""

        if (
            self.fyta.expiration is None
            or self.fyta.expiration.timestamp() < datetime.now().timestamp()
        ):
            await self.renew_authentication()

        return await self.fyta.update_all_plants()

    async def renew_authentication(self) -> bool:
        """Renew access token for FYTA API."""
        credentials: dict[str, str | datetime] = {}

        try:
            credentials = await self.fyta.login()
        except FytaConnectionError as ex:
            raise ConfigEntryNotReady from ex
        except (FytaAuthentificationError, FytaPasswordError) as ex:
            raise ConfigEntryAuthFailed from ex

        if isinstance(credentials["expiration"], datetime):
            credentials["expiration"] = credentials["expiration"].isoformat()

        new_config_entry = {**self.config_entry.data}
        new_config_entry["access_token"] = credentials.get("access_token")
        new_config_entry["expiration"] = credentials.get("expiration")

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_config_entry
        )

        _LOGGER.info("Credentials successfully updated")

        return True
