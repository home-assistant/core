"""DataUpdateCoordinator for ISS TLE data; updates default every 24 hours."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ..const import CONF_TLE_SOURCES, DEFAULT_TLE_SOURCES, TLE_SOURCES
from ..tle_fetcher import TleFetcher

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_INTERVAL = timedelta(hours=24)
ISS_NORAD_ID = 25544
STORAGE_VERSION = 1
STORAGE_KEY = "iss_tle_cache"


class IssTleCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches TLE data for the ISS."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: ConfigEntry,
        update_interval: timedelta = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize the ISS TLE coordinator."""
        store_path = f"{STORAGE_KEY}.{config_entry.entry_id}"
        _LOGGER.debug("Creating Store with path: %s", store_path)

        self._store: Store[dict[str, Any]] = Store[dict[str, Any]](
            hass,
            STORAGE_VERSION,
            store_path,
        )

        # Initialize TLE fetcher with proper User-Agent
        session = async_get_clientsession(hass)
        user_agent = f"HomeAssistant/{ha_version} (ISS Integration)"
        self._fetcher = TleFetcher(session, user_agent)

        super().__init__(
            hass,
            _LOGGER,
            name="ISS TLE Data",
            update_interval=update_interval,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest TLE data from multiple sources."""
        cached_data: dict[str, Any] | None = await self._store.async_load()
        cache_time: datetime | None = None

        _LOGGER.debug("Checking if TLE data needs to be refreshed")

        # Parse cached timestamp
        if cached_data is not None:
            timestamp_str = cached_data.get("timestamp")
            if isinstance(timestamp_str, str):
                try:
                    cache_time = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    _LOGGER.warning(
                        "Cached TLE data has invalid timestamp, ignoring cache"
                    )

        # Use cache if still valid
        if self.update_interval is not None and cache_time is not None:
            if datetime.now() - cache_time < self.update_interval:
                _LOGGER.debug(
                    "Using cached TLE data from %s",
                    timestamp_str or "unknown",
                )

                _LOGGER.debug("TLE data returned from cache")
                _LOGGER.debug(
                    "TLE data will be checked again in %s", self.update_interval
                )
                return cached_data  # type: ignore[return-value]

        # Build source list from configuration
        if self.config_entry is None:
            enabled_sources = DEFAULT_TLE_SOURCES
        else:
            enabled_sources = self.config_entry.options.get(
                CONF_TLE_SOURCES, DEFAULT_TLE_SOURCES
            )
        source_urls = [
            TLE_SOURCES[source] for source in enabled_sources if source in TLE_SOURCES
        ]

        # Fetch fresh TLE data from sources
        _LOGGER.debug("Fetching fresh TLE data for ISS (NORAD ID %d)", ISS_NORAD_ID)
        _LOGGER.debug("TLE sources configured: %s", enabled_sources)
        _LOGGER.debug("TLE URLs to try: %s", source_urls)

        valid_tle = await self._fetcher.fetch_tle(source_urls, ISS_NORAD_ID)

        # If no valid TLE found, fall back to cache
        if not valid_tle:
            if cached_data is not None:
                _LOGGER.warning(
                    "No valid TLE fetched from any source; using cached data from %s",
                    cached_data.get("timestamp", "unknown"),
                )
                return cached_data
            raise UpdateFailed("No valid TLE data could be fetched for ISS")

        # Prepare fresh data
        data: dict[str, Any] = {
            "line1": valid_tle[0],
            "line2": valid_tle[1],
            "timestamp": datetime.now().isoformat(),
        }

        # Cache fresh data
        await self._store.async_save(data)
        _LOGGER.debug("TLE data has been refreshed and cached")
        _LOGGER.debug("TLE data will be checked again in %s", self.update_interval)

        return data

    async def async_clear_cache(self) -> None:
        """Clear the TLE cache."""
        await self._store.async_remove()
