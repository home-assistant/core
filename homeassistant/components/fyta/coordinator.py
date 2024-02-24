"""Coordinator for FYTA integration."""

from datetime import datetime, timedelta
import logging

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


class FytaCoordinator(DataUpdateCoordinator[dict]):
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
        self.fyta: FytaConnector = fyta
        self._attr_last_update_success: datetime | None = None

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""

        if self.fyta.expiration is None or self.fyta.expiration < datetime.now():
            await self.renew_authentication()

        data = await self.fyta.update_all_plants()

        self._attr_last_update_success = datetime.now()
        return data

    async def renew_authentication(self) -> bool:
        """Renew access token for FYTA API."""

        try:
            await self.fyta.login()
        except FytaConnectionError as ex:
            raise ConfigEntryNotReady from ex
        except FytaAuthentificationError as ex:
            raise ConfigEntryAuthFailed from ex
        except FytaPasswordError as ex:
            raise ConfigEntryAuthFailed from ex

        return True
