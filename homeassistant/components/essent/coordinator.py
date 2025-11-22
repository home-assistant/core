"""DataUpdateCoordinator for Essent integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import random
from typing import Any

from essent_dynamic_pricing import (
    EssentClient,
    EssentConnectionError,
    EssentDataError,
    EssentError,
    EssentPrices,
    EssentResponseError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)
EssentData = dict[str, Any]
type EssentConfigEntry = ConfigEntry["EssentDataUpdateCoordinator"]


class EssentDataUpdateCoordinator(DataUpdateCoordinator[EssentData]):
    """Class to manage fetching Essent data."""

    config_entry: EssentConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: EssentConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=None,  # explicit scheduling
        )
        self._client = EssentClient(async_get_clientsession(hass))
        self._unsub_data: Callable[[], None] | None = None
        self._unsub_listener: Callable[[], None] | None = None
        # Random minute offset for API fetches (0-59 minutes)
        self._api_fetch_minute_offset = random.randint(0, 59)

    @property
    def api_fetch_minute_offset(self) -> int:
        """Return the configured minute offset for API fetches."""
        return self._api_fetch_minute_offset

    @property
    def api_refresh_scheduled(self) -> bool:
        """Return whether the API refresh task is scheduled."""
        return self._unsub_data is not None

    @property
    def listener_tick_scheduled(self) -> bool:
        """Return whether the listener tick task is scheduled."""
        return self._unsub_listener is not None

    def start_schedules(self) -> None:
        """Start both API fetch and listener tick schedules.

        This should be called after the first successful data fetch.
        Schedules will continue running regardless of API success/failure.
        """
        if self.config_entry.pref_disable_polling:
            _LOGGER.debug("Polling disabled by config entry, not starting schedules")
            return

        if self._unsub_data or self._unsub_listener:
            return

        _LOGGER.info(
            "Starting schedules: API fetch every hour at minute %d, "
            "listener updates on the hour",
            self._api_fetch_minute_offset,
        )
        self._schedule_data_refresh()
        self._schedule_listener_tick()

    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and ignore new runs."""
        await super().async_shutdown()
        if self._unsub_data:
            self._unsub_data()
            self._unsub_data = None
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    def _schedule_data_refresh(self) -> None:
        """Schedule next data fetch at a random minute offset within the hour."""
        if self._unsub_data:
            self._unsub_data()

        now = dt_util.utcnow()
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        candidate = (
            current_hour
            + UPDATE_INTERVAL
            + timedelta(minutes=self._api_fetch_minute_offset)
        )
        if candidate <= now:
            candidate = candidate + UPDATE_INTERVAL

        _LOGGER.debug(
            "Scheduling next API fetch for %s (offset: %d minutes)",
            candidate,
            self._api_fetch_minute_offset,
        )

        @callback
        def _handle(_: datetime) -> None:
            """Handle the scheduled API refresh trigger."""
            self._unsub_data = None
            self.hass.async_create_task(self.async_request_refresh())
            # Reschedule for next hour regardless of success/failure
            self._schedule_data_refresh()

        self._unsub_data = async_track_point_in_utc_time(self.hass, _handle, candidate)

    def _schedule_listener_tick(self) -> None:
        """Schedule listener updates on the hour to advance cached tariffs."""
        if self._unsub_listener:
            self._unsub_listener()

        now = dt_util.utcnow()
        next_hour = now + UPDATE_INTERVAL
        next_run = datetime(
            next_hour.year,
            next_hour.month,
            next_hour.day,
            next_hour.hour,
            tzinfo=dt_util.UTC,
        )

        _LOGGER.debug("Scheduling next listener tick for %s", next_run)

        @callback
        def _handle(_: datetime) -> None:
            """Handle the scheduled listener tick to update sensors."""
            self._unsub_listener = None
            _LOGGER.debug("Listener tick fired, updating sensors with cached data")
            self.async_update_listeners()
            self._schedule_listener_tick()

        self._unsub_listener = async_track_point_in_utc_time(
            self.hass,
            _handle,
            next_run,
        )

    async def _async_update_data(self) -> EssentData:
        """Fetch data from API."""
        try:
            prices: EssentPrices = await self._client.async_get_prices()
            return prices.to_dict()
        except EssentConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except EssentResponseError as err:
            raise UpdateFailed(str(err)) from err
        except EssentDataError as err:
            _LOGGER.debug("Invalid data received: %s", err)
            raise UpdateFailed(str(err)) from err
        except EssentError as err:
            raise UpdateFailed("Unexpected Essent error") from err
