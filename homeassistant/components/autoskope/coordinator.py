"""Data update coordinator for the Autoskope integration."""

from __future__ import annotations

import logging

from autoskope_client.api import AutoskopeApi
from autoskope_client.models import CannotConnect, InvalidAuth, Vehicle
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


type AutoskopeConfigEntry = ConfigEntry[AutoskopeDataUpdateCoordinator]


class AutoskopeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Vehicle]]):
    """Class to manage fetching Autoskope data."""

    config_entry: AutoskopeConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: AutoskopeApi, entry: AutoskopeConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Vehicle]:
        """Fetch data from API endpoint."""
        try:
            vehicles = await self.api.get_vehicles()
            return {vehicle.id: vehicle for vehicle in vehicles}

        except InvalidAuth as err:
            # Attempt to re-authenticate using stored credentials
            try:
                await self.api.authenticate()
                # Retry the request after successful re-authentication
                vehicles = await self.api.get_vehicles()
                return {vehicle.id: vehicle for vehicle in vehicles}
            except InvalidAuth:
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error communicating with API: {err}"
            ) from err
