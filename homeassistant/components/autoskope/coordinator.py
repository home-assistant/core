"""Data update coordinator for the Autoskope integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from autoskope_client.api import AutoskopeApi
from autoskope_client.models import CannotConnect, InvalidAuth, Vehicle
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class AutoskopeRuntimeData:
    """Runtime data for the Autoskope integration."""

    coordinator: AutoskopeDataUpdateCoordinator


type AutoskopeConfigEntry = ConfigEntry[AutoskopeRuntimeData]


class AutoskopeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Vehicle]]):
    """Class to manage fetching Autoskope data."""

    config_entry: AutoskopeConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: AutoskopeApi, entry: AutoskopeConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        _LOGGER.debug(
            "Initializing coordinator with update interval: %s", UPDATE_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.config_entry = entry
        # Flag to log unavailability only once
        self._logged_unavailability: bool = False

    async def _async_update_data(self) -> dict[str, Vehicle]:
        """Fetch data from API endpoint."""
        _LOGGER.debug("Starting data update")

        try:
            vehicles = await self.api.get_vehicles(
                session=async_get_clientsession(self.hass)
            )

            if self._logged_unavailability:
                _LOGGER.info("Connection to Autoskope restored")
                self._logged_unavailability = False

            return {vehicle.id: vehicle for vehicle in vehicles}

        except InvalidAuth as err:
            _LOGGER.debug("Authentication failed, attempting re-authentication")

            # Attempt to re-authenticate using stored credentials
            try:
                await self.api.authenticate(session=async_get_clientsession(self.hass))
                _LOGGER.info("Re-authentication successful, retrying data fetch")

                # Retry the request after successful re-authentication
                vehicles = await self.api.get_vehicles(
                    session=async_get_clientsession(self.hass)
                )

                if self._logged_unavailability:
                    _LOGGER.info(
                        "Connection to Autoskope restored after re-authentication"
                    )
                    self._logged_unavailability = False

                return {vehicle.id: vehicle for vehicle in vehicles}

            except (InvalidAuth, Exception) as reauth_err:
                if not self._logged_unavailability:
                    _LOGGER.error(
                        "Re-authentication failed with Autoskope: %s", reauth_err
                    )
                    self._logged_unavailability = True
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

        except CannotConnect as err:
            if not self._logged_unavailability:
                _LOGGER.error("Error connecting to Autoskope: %s", err)
                self._logged_unavailability = True
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        except Exception as err:
            if not self._logged_unavailability:
                _LOGGER.exception("Unexpected error fetching autoskope data")
                self._logged_unavailability = True
            raise UpdateFailed(
                f"Unexpected error communicating with API: {err}"
            ) from err
