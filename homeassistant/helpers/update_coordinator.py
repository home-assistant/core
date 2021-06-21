"""Helpers to help coordinate updates."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from datetime import datetime, timedelta
import logging
from time import monotonic
from typing import Callable, Generic, TypeVar
import urllib.error

import aiohttp
import requests

from homeassistant import config_entries
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity, event
from homeassistant.util.dt import utcnow

from .debounce import Debouncer

REQUEST_REFRESH_DEFAULT_COOLDOWN = 10
REQUEST_REFRESH_DEFAULT_IMMEDIATE = True

T = TypeVar("T")


class UpdateFailed(Exception):
    """Raised when an update has failed."""


class DataUpdateCoordinator(Generic[T]):
    """Class to manage fetching data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        name: str,
        update_interval: timedelta | None = None,
        update_method: Callable[[], Awaitable[T]] | None = None,
        request_refresh_debouncer: Debouncer | None = None,
    ) -> None:
        """Initialize global data updater."""
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_method = update_method
        self.update_interval = update_interval
        self.config_entry = config_entries.current_entry.get()

        # It's None before the first successful update.
        # Components should call async_config_entry_first_refresh
        # to make sure the first update was successful.
        # Set type to just T to remove annoying checks that data is not None
        # when it was already checked during setup.
        self.data: T = None  # type: ignore[assignment]

        self._listeners: list[CALLBACK_TYPE] = []
        self._job = HassJob(self._handle_refresh_interval)
        self._unsub_refresh: CALLBACK_TYPE | None = None
        self._request_refresh_task: asyncio.TimerHandle | None = None
        self.last_update_success = True
        self.last_exception: Exception | None = None

        if request_refresh_debouncer is None:
            request_refresh_debouncer = Debouncer(
                hass,
                logger,
                cooldown=REQUEST_REFRESH_DEFAULT_COOLDOWN,
                immediate=REQUEST_REFRESH_DEFAULT_IMMEDIATE,
                function=self.async_refresh,
            )
        else:
            request_refresh_debouncer.function = self.async_refresh

        self._debounced_refresh = request_refresh_debouncer

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        """Listen for data updates."""
        schedule_refresh = not self._listeners

        self._listeners.append(update_callback)

        # This is the first listener, set up interval.
        if schedule_refresh:
            self._schedule_refresh()

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self.async_remove_listener(update_callback)

        return remove_listener

    @callback
    def async_remove_listener(self, update_callback: CALLBACK_TYPE) -> None:
        """Remove data update."""
        self._listeners.remove(update_callback)

        if not self._listeners and self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

    @callback
    def _schedule_refresh(self) -> None:
        """Schedule a refresh."""
        if self.update_interval is None:
            return

        if self.config_entry and self.config_entry.pref_disable_polling:
            return

        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

        # We _floor_ utcnow to create a schedule on a rounded second,
        # minimizing the time between the point and the real activation.
        # That way we obtain a constant update frequency,
        # as long as the update process takes less than a second
        self._unsub_refresh = event.async_track_point_in_utc_time(
            self.hass,
            self._job,
            utcnow().replace(microsecond=0) + self.update_interval,
        )

    async def _handle_refresh_interval(self, _now: datetime) -> None:
        """Handle a refresh interval occurrence."""
        self._unsub_refresh = None
        await self._async_refresh(log_failures=True, scheduled=True)

    async def async_request_refresh(self) -> None:
        """Request a refresh.

        Refresh will wait a bit to see if it can batch them.
        """
        await self._debounced_refresh.async_call()

    async def _async_update_data(self) -> T:
        """Fetch the latest data from the source."""
        if self.update_method is None:
            raise NotImplementedError("Update method not implemented")
        return await self.update_method()

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup.

        Will automatically raise ConfigEntryNotReady if the refresh
        fails. Additionally logging is handled by config entry setup
        to ensure that multiple retries do not cause log spam.
        """
        await self._async_refresh(log_failures=False, raise_on_auth_failed=True)
        if self.last_update_success:
            return
        ex = ConfigEntryNotReady()
        ex.__cause__ = self.last_exception
        raise ex

    async def async_refresh(self) -> None:
        """Refresh data and log errors."""
        await self._async_refresh(log_failures=True)

    async def _async_refresh(  # noqa: C901
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
    ) -> None:
        """Refresh data."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

        self._debounced_refresh.async_cancel()

        if scheduled and self.hass.is_stopping:
            return

        start = monotonic()
        auth_failed = False

        try:
            self.data = await self._async_update_data()

        except (asyncio.TimeoutError, requests.exceptions.Timeout) as err:
            self.last_exception = err
            if self.last_update_success:
                if log_failures:
                    self.logger.error("Timeout fetching %s data", self.name)
                self.last_update_success = False

        except (aiohttp.ClientError, requests.exceptions.RequestException) as err:
            self.last_exception = err
            if self.last_update_success:
                if log_failures:
                    self.logger.error("Error requesting %s data: %s", self.name, err)
                self.last_update_success = False

        except urllib.error.URLError as err:
            self.last_exception = err
            if self.last_update_success:
                if log_failures:
                    if err.reason == "timed out":
                        self.logger.error("Timeout fetching %s data", self.name)
                    else:
                        self.logger.error(
                            "Error requesting %s data: %s", self.name, err
                        )
                self.last_update_success = False

        except UpdateFailed as err:
            self.last_exception = err
            if self.last_update_success:
                if log_failures:
                    self.logger.error("Error fetching %s data: %s", self.name, err)
                self.last_update_success = False

        except ConfigEntryAuthFailed as err:
            auth_failed = True
            self.last_exception = err
            if self.last_update_success:
                if log_failures:
                    self.logger.error(
                        "Authentication failed while fetching %s data: %s",
                        self.name,
                        err,
                    )
                self.last_update_success = False
            if raise_on_auth_failed:
                raise

            if self.config_entry:
                self.config_entry.async_start_reauth(self.hass)
        except NotImplementedError as err:
            self.last_exception = err
            raise err

        except Exception as err:  # pylint: disable=broad-except
            self.last_exception = err
            self.last_update_success = False
            if log_failures:
                self.logger.exception(
                    "Unexpected error fetching %s data: %s", self.name, err
                )

        else:
            if not self.last_update_success:
                self.last_update_success = True
                self.logger.info("Fetching %s data recovered", self.name)

        finally:
            self.logger.debug(
                "Finished fetching %s data in %.3f seconds",
                self.name,
                monotonic() - start,
            )
            if not auth_failed and self._listeners and not self.hass.is_stopping:
                self._schedule_refresh()

        for update_callback in self._listeners:
            update_callback()

    @callback
    def async_set_updated_data(self, data: T) -> None:
        """Manually update data, notify listeners and reset refresh interval."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

        self._debounced_refresh.async_cancel()

        self.data = data
        self.last_update_success = True
        self.logger.debug(
            "Manually updated %s data",
            self.name,
        )

        if self._listeners:
            self._schedule_refresh()

        for update_callback in self._listeners:
            update_callback()

    @callback
    def _async_stop_refresh(self, _: Event) -> None:
        """Stop refreshing when Home Assistant is stopping."""
        self.update_interval = None
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None


class CoordinatorEntity(Generic[T], entity.Entity):
    """A class for entities using DataUpdateCoordinator."""

    def __init__(self, coordinator: DataUpdateCoordinator[T]) -> None:
        """Create the entity with a DataUpdateCoordinator."""
        self.coordinator = coordinator

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        # Ignore manual update requests if the entity is disabled
        if not self.enabled:
            return

        await self.coordinator.async_request_refresh()
