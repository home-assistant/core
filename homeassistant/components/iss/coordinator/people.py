"""DataUpdateCoordinator for ISS people in space; updates default every 24 hours."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from pyiss import ISS

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_INTERVAL = timedelta(hours=24)
MAX_RETRIES = 3
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 8  # seconds


class IssPeopleCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator that fetches the current number of people in space for the ISS integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: ConfigEntry,
        update_interval: timedelta = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize the ISS People coordinator.

        Args:
            hass: Home Assistant instance.
            update_interval: Frequency at which data is refreshed.
        """
        self._iss = ISS()

        super().__init__(
            hass,
            _LOGGER,
            name="ISS People in Space",
            update_interval=update_interval,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> dict:
        """Fetch the latest people-in-space data from the API with retries."""
        backoff = INITIAL_BACKOFF

        # Inner function to comply with TRY301 linting rule
        def _raise_invalid_payload() -> None:
            raise UpdateFailed("Invalid people-in-space payload")

        for attempt in range(MAX_RETRIES):
            _LOGGER.debug(
                "Fetching people data (attempt %d/%d)", attempt + 1, MAX_RETRIES
            )

            try:
                data = await self.hass.async_add_executor_job(self._iss.people_in_space)

                # Minimal validation
                if "number" not in data or "people" not in data:
                    _LOGGER.warning(
                        "Invalid people-in-space payload (attempt %d/%d)",
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    _raise_invalid_payload()
            except Exception as err:
                _LOGGER.warning(
                    "Error fetching people data (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_RETRIES,
                    err,
                )
                if attempt == MAX_RETRIES - 1:
                    raise UpdateFailed(
                        f"Error fetching people in space: {err}"
                    ) from err

                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
            else:
                _LOGGER.debug("People data successfully fetched")
                return data

        raise UpdateFailed("Failed to fetch people data after retries")
