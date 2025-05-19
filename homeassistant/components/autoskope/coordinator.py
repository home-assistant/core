"""Data update coordinator for the Autoskope integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL
from .models import AutoskopeApi, CannotConnect, InvalidAuth, Vehicle

_LOGGER = logging.getLogger(__name__)

# Default scan interval used by options flow and tests
DEFAULT_SCAN_INTERVAL = 60


class AutoskopeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Vehicle]]):
    """Class to manage fetching Autoskope data."""

    def __init__(
        self, hass: HomeAssistant, api: AutoskopeApi, entry: ConfigEntry
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
        self.entry = entry
        # Flag to log unavailability only once
        self._logged_unavailability: bool = False

    async def _async_update_data(self) -> dict[str, Vehicle]:
        """Fetch data from API endpoint."""
        _LOGGER.debug("Starting data update")
        error_to_raise: Exception | None = None
        vehicles_dict: dict[str, Vehicle] = {}

        try:
            vehicles = await self.api.get_vehicles()

            # If we reached here, the update was successful, reset log flag
            if self._logged_unavailability:
                _LOGGER.info("Connection to Autoskope restored")
                self._logged_unavailability = False

            # Process vehicles into a dictionary keyed by ID
            if isinstance(vehicles, list):
                vehicles_dict = {v.id: v for v in vehicles}
            else:
                _LOGGER.warning(  # type: ignore[unreachable]
                    "Received unexpected data format from get_vehicles: %s",
                    type(vehicles),
                )
                # Store error to raise after try block
                error_to_raise = UpdateFailed(
                    f"Unexpected data format: {type(vehicles)}"
                )

        except InvalidAuth as err:
            # Log authentication error once and raise ConfigEntryAuthFailed
            if not self._logged_unavailability:
                _LOGGER.error("Authentication error with Autoskope: %s", err)
                self._logged_unavailability = True
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

        except (CannotConnect, UpdateFailed) as err:
            # Log connection/update error once and raise UpdateFailed
            if not self._logged_unavailability:
                _LOGGER.error("Error connecting to Autoskope: %s", err)
                self._logged_unavailability = True
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        except Exception as err:
            # Log other unexpected errors once and raise UpdateFailed
            if not self._logged_unavailability:
                _LOGGER.exception("Unexpected error fetching autoskope data")
                self._logged_unavailability = True
            raise UpdateFailed(
                f"Unexpected error communicating with API: {err}"
            ) from err

        # Raise any stored error after the try block
        if error_to_raise:
            raise error_to_raise

        return vehicles_dict
