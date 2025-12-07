"""Coordinator for Diyanet integration."""

from collections.abc import Callable
from datetime import date, datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DiyanetApiClient, DiyanetConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DiyanetCoordinator(DataUpdateCoordinator[dict]):
    """Diyanet data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: DiyanetApiClient,
        location_id: int,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=None,
            config_entry=config_entry,
        )
        self.client = client
        self.location_id = location_id
        self._unsub_timer: Callable[[], None] | None = None
        self._store: Store[dict[str, Any]] = Store(
            hass, version=1, key=f"diyanet_{config_entry.entry_id}"
        )
        self._loaded_from_cache = False
        self._force_refresh = False

    async def async_setup(self) -> None:
        """Set up the coordinator with daily updates at 00:05."""
        # Schedule daily update at 00:05
        self._unsub_timer = async_track_time_change(
            self.hass,
            self._scheduled_update,
            hour=0,
            minute=5,
            second=0,
        )

    async def _scheduled_update(self, now: datetime) -> None:
        """Handle scheduled update."""
        _LOGGER.debug("Running scheduled prayer times update at %s", now)
        await self.async_request_refresh()

    def shutdown(self) -> None:
        """Unload the coordinator."""
        if self._unsub_timer:
            self._unsub_timer()

    async def async_force_refresh(self) -> None:
        """Force a refresh by bypassing the cache."""
        self._force_refresh = True
        try:
            await self.async_request_refresh()
        finally:
            self._force_refresh = False

    async def _async_update_data(self) -> dict:
        """Fetch data from Diyanet API, using cache if valid."""
        today = date.today()

        # Skip cache if force refresh is requested
        if not self._force_refresh:
            # Try to load cached data first
            cached = await self._store.async_load()
            if isinstance(cached, dict):
                # Support two formats:
                # 1) Wrapper: {"cache_date": "YYYY-MM-DD", "data": {...}}
                # 2) Legacy:  {...} (raw API payload)
                cached_payload: dict | None = None
                cached_dt: date | None = None

                if (
                    "cache_date" in cached
                    and "data" in cached
                    and isinstance(cached["data"], dict)
                ):
                    # New wrapper format
                    try:
                        cached_dt = date.fromisoformat(str(cached["cache_date"]))
                    except Exception:  # noqa: BLE001
                        cached_dt = None
                    cached_payload = cached["data"]
                else:
                    # Legacy raw payload
                    cached_payload = cached
                    # Best-effort extraction of date
                    # Prefer an ISO field if present
                    iso_field = cached.get("gregorianDate")
                    if isinstance(iso_field, str):
                        try:
                            cached_dt = date.fromisoformat(iso_field)
                        except Exception:  # noqa: BLE001
                            cached_dt = None
                    if cached_dt is None and (
                        long_field := cached.get("gregorianDateLong")
                    ):
                        # Example format: "29 November 2025" (locale dependent)
                        try:
                            cached_dt = datetime.strptime(long_field, "%d %B %Y").date()
                        except Exception:  # noqa: BLE001
                            cached_dt = None

                if cached_payload is not None and cached_dt == today:
                    _LOGGER.debug("Using cached prayer times for today")
                    self._loaded_from_cache = True
                    return cached_payload
        else:
            _LOGGER.debug("Force refresh requested, skipping cache")

        # If no valid cache or force refresh, fetch new data
        try:
            _LOGGER.debug("Fetching prayer times for location %s", self.location_id)
            data = await self.client.get_prayer_times(self.location_id)
        except DiyanetConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            _LOGGER.debug("Prayer times updated successfully, saving to cache")
            # Save in wrapper format with ISO cache date for robust comparisons
            await self._store.async_save(
                {"cache_date": today.isoformat(), "data": data}
            )
            self._loaded_from_cache = False
            return data
