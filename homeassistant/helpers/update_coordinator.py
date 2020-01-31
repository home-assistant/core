"""Helpers to help coordinate updates."""
import asyncio
from datetime import datetime, timedelta
import logging
from time import monotonic
from typing import Any, Awaitable, Callable, List, Optional

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .debounce import Debouncer


class UpdateFailed(Exception):
    """Raised when an update has failed."""


class DataUpdateCoordinator:
    """Class to manage fetching data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        update_method: Callable[[], Awaitable],
        update_interval: timedelta,
        request_refresh_debouncer: Debouncer,
    ):
        """Initialize global data updater."""
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_method = update_method
        self.update_interval = update_interval

        self.data: Optional[Any] = None

        self._listeners: List[CALLBACK_TYPE] = []
        self._unsub_refresh: Optional[CALLBACK_TYPE] = None
        self._request_refresh_task: Optional[asyncio.TimerHandle] = None
        self.failed_last_update = False
        self._debounced_refresh = request_refresh_debouncer
        request_refresh_debouncer.function = self._async_do_refresh

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> None:
        """Listen for data updates."""
        schedule_refresh = not self._listeners

        self._listeners.append(update_callback)

        # This is the first listener, set up interval.
        if schedule_refresh:
            self._schedule_refresh()

    @callback
    def async_remove_listener(self, update_callback: CALLBACK_TYPE) -> None:
        """Remove data update."""
        self._listeners.remove(update_callback)

        if not self._listeners and self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

    async def async_refresh(self) -> None:
        """Refresh the data."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

        await self._async_do_refresh()

    @callback
    def _schedule_refresh(self) -> None:
        """Schedule a refresh."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

        self._unsub_refresh = async_track_point_in_utc_time(
            self.hass, self._handle_refresh_interval, utcnow() + self.update_interval
        )

    async def _handle_refresh_interval(self, _now: datetime) -> None:
        """Handle a refresh interval occurrence."""
        self._unsub_refresh = None
        await self._async_do_refresh()

    async def async_request_refresh(self) -> None:
        """Request a refresh.

        Refresh will wait a bit to see if it can batch them.
        """
        await self._debounced_refresh.async_call()

    async def _async_do_refresh(self) -> None:
        """Time to update."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

        self._debounced_refresh.async_cancel()

        try:
            start = monotonic()
            self.data = await self.update_method()

        except UpdateFailed as err:
            if not self.failed_last_update:
                self.logger.error("Error fetching %s data: %s", self.name, err)
                self.failed_last_update = True

        except Exception as err:  # pylint: disable=broad-except
            self.failed_last_update = True
            self.logger.exception(
                "Unexpected error fetching %s data: %s", self.name, err
            )

        else:
            if self.failed_last_update:
                self.failed_last_update = False
                self.logger.info("Fetching %s data recovered")

        finally:
            self.logger.debug(
                "Finished fetching %s data in %.3f seconds",
                self.name,
                monotonic() - start,
            )
            self._schedule_refresh()

        for update_callback in self._listeners:
            update_callback()
