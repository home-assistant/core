"""Coordinator for FYTA integration."""

from datetime import datetime, timedelta
import logging

from fyta_cli.fyta_connector import FytaConnector

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class FytaCoordinator(DataUpdateCoordinator):
    """Fyta custom coordinator."""
    
    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, fyta: FytaConnector
    ) -> None:
        """Initialize my coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name="FYTA Coordinator",
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=60),
        )

        self.fyta = fyta

        self.plant_list: dict[int, str] = {}
        self.access_token = ""
        self.expiration = None
        self._attr_last_update_success = None

    async def _async_update_data(self):
        """Fetch data from API endpoint."""

        if self.access_token == "" or self.expiration < datetime.now():
            await self.renew_authentication()

        data = await self.fyta.update_all_plants()
        data |= {"online": True}

        self.plant_list = self.fyta.plant_list
        data |= {"plant_number": len(self.plant_list)}
        data |= {"email": self.fyta.email}
        data |= {"name": "Fyta Coordinator"}

        self._attr_last_update_success = datetime.now()
        return data

    async def renew_authentication(self) -> bool:
        """Renew access token for FYTA API."""

        await self.fyta.login()

        self.access_token = self.fyta.access_token
        self.expiration = self.fyta.expiration

        return True
