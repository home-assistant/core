"""DataUpdateCoordinator for ISS people in space; updates default every 24 hours."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.loader import async_get_integration

_LOGGER = logging.getLogger(__name__)

DEFAULT_PEOPLE_URL = "http://api.open-notify.org/astros.json"
DEFAULT_UPDATE_INTERVAL = timedelta(hours=24)
REQUEST_TIMEOUT = timedelta(seconds=10)
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
        url: str = DEFAULT_PEOPLE_URL,
        update_interval: timedelta = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize the ISS People coordinator.

        Args:
            hass: Home Assistant instance.
            url: URL to fetch the people-in-space JSON data.
            update_interval: Frequency at which data is refreshed.
        """
        self._url = url
        self._session = async_get_clientsession(hass)

        super().__init__(
            hass,
            _LOGGER,
            name="ISS People in Space",
            update_interval=update_interval,
            config_entry=config_entry,
        )

    async def _fetch_with_retry(
        self, headers: dict[str, str], attempt: int, backoff: float
    ) -> dict:
        """Attempt to fetch people data with proper error handling."""
        async with asyncio.timeout(REQUEST_TIMEOUT.total_seconds()):
            resp = await self._session.get(self._url, headers=headers)

        if resp.status != 200:
            _LOGGER.warning(
                "Unexpected status %d (attempt %d/%d)",
                resp.status,
                attempt + 1,
                MAX_RETRIES,
            )
            raise UpdateFailed(f"Unexpected status {resp.status}")

        data = await resp.json()

        # Minimal validation
        if "number" not in data or "people" not in data:
            _LOGGER.warning(
                "Invalid people-in-space payload (attempt %d/%d)",
                attempt + 1,
                MAX_RETRIES,
            )
            raise UpdateFailed("Invalid people-in-space payload")

        return data

    async def _async_update_data(self) -> dict:
        """Fetch the latest people-in-space data from the API with retries."""
        integration = await async_get_integration(self.hass, "iss")
        integration_version = integration.version or "unknown"
        headers = {
            "User-Agent": f"HomeAssistant/HA_VERSION ISSIntegration/{integration_version}"
        }

        last_exception: Exception | None = None
        backoff = INITIAL_BACKOFF

        for attempt in range(MAX_RETRIES):
            try:
                _LOGGER.debug(
                    "Fetching people data (attempt %d/%d)", attempt + 1, MAX_RETRIES
                )
                data = await self._fetch_with_retry(headers, attempt, backoff)
            except TimeoutError as err:
                _LOGGER.debug(
                    "Timeout fetching people data (attempt %d/%d)",
                    attempt + 1,
                    MAX_RETRIES,
                )
                last_exception = err
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    continue
                raise UpdateFailed("Timeout fetching people in space") from err
            except ClientError as err:
                _LOGGER.warning(
                    "Client error fetching people data (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_RETRIES,
                    err,
                )
                last_exception = err
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    continue
                raise UpdateFailed(f"Error fetching people in space: {err}") from err
            except UpdateFailed:
                # Re-raise UpdateFailed from validation errors
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    continue
                raise
            else:
                # Success - return the data
                _LOGGER.debug("People data successfully fetched")
                return data

        # Should never reach here, but just in case
        if last_exception:
            raise UpdateFailed(
                "Failed to fetch people data after retries"
            ) from last_exception
        raise UpdateFailed("Failed to fetch people data after retries")
