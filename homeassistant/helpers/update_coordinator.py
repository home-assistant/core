"""Helpers to help coordinate updates."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Generator
from datetime import datetime, timedelta
import logging
from random import randint
from time import monotonic
from typing import Any, Generic, Protocol, TypeVar
import urllib.error

import aiohttp
import requests

from homeassistant import config_entries
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.util.dt import utcnow

from . import entity, event
from .debounce import Debouncer

REQUEST_REFRESH_DEFAULT_COOLDOWN = 10
REQUEST_REFRESH_DEFAULT_IMMEDIATE = True

_T = TypeVar("_T")
_BaseDataUpdateCoordinatorT = TypeVar(
    "_BaseDataUpdateCoordinatorT", bound="BaseDataUpdateCoordinatorProtocol"
)
_DataUpdateCoordinatorT = TypeVar(
    "_DataUpdateCoordinatorT", bound="DataUpdateCoordinator[Any]"
)


class UpdateFailed(Exception):
    """Raised when an update has failed."""


class BaseDataUpdateCoordinatorProtocol(Protocol):
    """Base protocol type for DataUpdateCoordinator."""

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Listen for data updates."""


class DataUpdateCoordinator(BaseDataUpdateCoordinatorProtocol, Generic[_T]):
    """Class to manage fetching data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        name: str,
        update_interval: timedelta | None = None,
        update_method: Callable[[], Awaitable[_T]] | None = None,
        request_refresh_debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        """Initialize global data updater."""
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_method = update_method
        self.update_interval = update_interval
        self._shutdown_requested = False
        self.config_entry = config_entries.current_entry.get()

        # It's None before the first successful update.
        # Components should call async_config_entry_first_refresh
        # to make sure the first update was successful.
        # Set type to just T to remove annoying checks that data is not None
        # when it was already checked during setup.
        self.data: _T = None  # type: ignore[assignment]

        # Pick a random microsecond to stagger the refreshes
        # and avoid a thundering herd.
        self._microsecond = randint(
            event.RANDOM_MICROSECOND_MIN, event.RANDOM_MICROSECOND_MAX
        )

        self._listeners: dict[CALLBACK_TYPE, tuple[CALLBACK_TYPE, object | None]] = {}
        job_name = "DataUpdateCoordinator"
        type_name = type(self).__name__
        if type_name != job_name:
            job_name += f" {type_name}"
        job_name += f" {name}"
        if entry := self.config_entry:
            job_name += f" {entry.title} {entry.domain} {entry.entry_id}"
        self._job = HassJob(self._handle_refresh_interval, job_name)
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

        if self.config_entry:
            self.config_entry.async_on_unload(self.async_shutdown)

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Listen for data updates."""
        schedule_refresh = not self._listeners

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._listeners.pop(remove_listener)
            if not self._listeners:
                self._unschedule_refresh()

        self._listeners[remove_listener] = (update_callback, context)

        # This is the first listener, set up interval.
        if schedule_refresh:
            self._schedule_refresh()

        return remove_listener

    @callback
    def async_update_listeners(self) -> None:
        """Update all registered listeners."""
        for update_callback, _ in list(self._listeners.values()):
            update_callback()

    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and ignore new runs."""
        self._shutdown_requested = True
        self._async_unsub_refresh()
        await self._debounced_refresh.async_shutdown()

    @callback
    def _unschedule_refresh(self) -> None:
        """Unschedule any pending refresh since there is no longer any listeners."""
        self._async_unsub_refresh()
        self._debounced_refresh.async_cancel()

    def async_contexts(self) -> Generator[Any, None, None]:
        """Return all registered contexts."""
        yield from (
            context for _, context in self._listeners.values() if context is not None
        )

    def _async_unsub_refresh(self) -> None:
        """Cancel any scheduled call."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

    @callback
    def _schedule_refresh(self) -> None:
        """Schedule a refresh."""
        if self.update_interval is None:
            return

        if self.config_entry and self.config_entry.pref_disable_polling:
            return

        # We do not cancel the debouncer here. If the refresh interval is shorter
        # than the debouncer cooldown, this would cause the debounce to never be called
        self._async_unsub_refresh()

        # We _floor_ utcnow to create a schedule on a rounded second,
        # minimizing the time between the point and the real activation.
        # That way we obtain a constant update frequency,
        # as long as the update process takes less than 500ms
        #
        # We do not align everything to happen at microsecond 0
        # since it increases the risk of a thundering herd
        # when multiple coordinators are scheduled to update at the same time.
        #
        # https://github.com/home-assistant/core/issues/82231
        self._unsub_refresh = event.async_track_point_in_utc_time(
            self.hass,
            self._job,
            utcnow().replace(microsecond=self._microsecond) + self.update_interval,
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

    async def _async_update_data(self) -> _T:
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
        await self._async_refresh(
            log_failures=False, raise_on_auth_failed=True, raise_on_entry_error=True
        )
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
        raise_on_entry_error: bool = False,
    ) -> None:
        """Refresh data."""
        self._async_unsub_refresh()
        self._debounced_refresh.async_cancel()

        if self._shutdown_requested or scheduled and self.hass.is_stopping:
            return

        if log_timing := self.logger.isEnabledFor(logging.DEBUG):
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

        except ConfigEntryError as err:
            self.last_exception = err
            if self.last_update_success:
                if log_failures:
                    self.logger.error(
                        "Config entry setup failed while fetching %s data: %s",
                        self.name,
                        err,
                    )
                self.last_update_success = False
            if raise_on_entry_error:
                raise

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
            self.logger.exception(
                "Unexpected error fetching %s data: %s", self.name, err
            )

        else:
            if not self.last_update_success:
                self.last_update_success = True
                self.logger.info("Fetching %s data recovered", self.name)

        finally:
            if log_timing:
                self.logger.debug(
                    "Finished fetching %s data in %.3f seconds (success: %s)",
                    self.name,
                    monotonic() - start,
                    self.last_update_success,
                )
            if not auth_failed and self._listeners and not self.hass.is_stopping:
                self._schedule_refresh()

        self.async_update_listeners()

    @callback
    def async_set_update_error(self, err: Exception) -> None:
        """Manually set an error, log the message and notify listeners."""
        self.last_exception = err
        if self.last_update_success:
            self.logger.error("Error requesting %s data: %s", self.name, err)
            self.last_update_success = False
            self.async_update_listeners()

    @callback
    def async_set_updated_data(self, data: _T) -> None:
        """Manually update data, notify listeners and reset refresh interval."""
        self._async_unsub_refresh()
        self._debounced_refresh.async_cancel()

        self.data = data
        self.last_update_success = True
        self.logger.debug(
            "Manually updated %s data",
            self.name,
        )

        if self._listeners:
            self._schedule_refresh()

        self.async_update_listeners()


class BaseCoordinatorEntity(entity.Entity, Generic[_BaseDataUpdateCoordinatorT]):
    """Base class for all Coordinator entities."""

    def __init__(
        self, coordinator: _BaseDataUpdateCoordinatorT, context: Any = None
    ) -> None:
        """Create the entity with a DataUpdateCoordinator."""
        self.coordinator = coordinator
        self.coordinator_context = context

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update, self.coordinator_context
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @abstractmethod
    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """


class CoordinatorEntity(BaseCoordinatorEntity[_DataUpdateCoordinatorT]):
    """A class for entities using DataUpdateCoordinator."""

    def __init__(
        self, coordinator: _DataUpdateCoordinatorT, context: Any = None
    ) -> None:
        """Create the entity with a DataUpdateCoordinator.

        Passthrough to BaseCoordinatorEntity.

        Necessary to bind TypeVar to correct scope.
        """
        super().__init__(coordinator, context)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        # Ignore manual update requests if the entity is disabled
        if not self.enabled:
            return

        await self.coordinator.async_request_refresh()
