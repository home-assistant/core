"""DataUpdateCoordinator for Essent integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging

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
type EssentConfigEntry = ConfigEntry[EssentDataUpdateCoordinator]


class EssentDataUpdateCoordinator(DataUpdateCoordinator[EssentPrices]):
    """Class to manage fetching Essent data."""

    config_entry: EssentConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: EssentConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._client = EssentClient(async_get_clientsession(hass))
        self._unsub_listener: Callable[[], None] | None = None

    def start_listener_schedule(self) -> None:
        """Start listener tick schedule after first successful data fetch."""
        if self.config_entry.pref_disable_polling:
            _LOGGER.debug("Polling disabled by config entry, not starting listener")
            return
        if self._unsub_listener:
            return
        _LOGGER.info("Starting listener updates on the hour")
        self._schedule_listener_tick()

    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and ignore new runs."""
        await super().async_shutdown()
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    def _schedule_listener_tick(self) -> None:
        """Schedule listener updates on the hour to advance cached tariffs."""
        if self._unsub_listener:
            self._unsub_listener()

        now = dt_util.utcnow()
        next_hour = now + timedelta(hours=1)
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

    async def _async_update_data(self) -> EssentPrices:
        """Fetch data from API."""
        try:
            return await self._client.async_get_prices()
        except EssentConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except EssentResponseError as err:
            raise UpdateFailed(str(err)) from err
        except EssentDataError as err:
            _LOGGER.debug("Invalid data received: %s", err)
            raise UpdateFailed(str(err)) from err
        except EssentError as err:
            raise UpdateFailed("Unexpected Essent error") from err
