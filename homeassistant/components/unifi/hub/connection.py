"""Manage the UniFi Network API session and reconnect policy."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiounifi

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import LOGGER

if TYPE_CHECKING:
    from .. import UnifiConfigEntry

CONNECTION_STABLE_PERIOD = 60


@dataclass
class BackoffPolicy:
    """Exponential retry delay capped at a maximum interval."""

    base: float = 15
    factor: float = 2
    maximum: float = 300

    def next_delay(self, attempt: int) -> float:
        """Return the delay in seconds for a zero-based attempt number."""
        delay = self.base
        for _ in range(attempt):
            if delay >= self.maximum:
                return self.maximum
            delay *= self.factor
        return min(delay, self.maximum)


class UnifiConnectionManager:
    """Own the API session state independently of its update transports."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: UnifiConfigEntry,
        api: aiounifi.Controller,
        signal: str,
    ) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = api
        self.signal = signal
        self.available = True

        self._backoff = BackoffPolicy()
        self._attempt = 0
        self._retry_handle: asyncio.TimerHandle | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._stable_handle: asyncio.TimerHandle | None = None
        self._recovering = False
        self._recovery_failed = False
        self._recovery_callback: Callable[[], Awaitable[None]] | None = None
        self._reauth_required = False
        self._stopped = False

    @callback
    def set_recovery_callback(
        self, callback_fn: Callable[[], Awaitable[None]] | None
    ) -> None:
        """Set the coroutine run after the Network application is ready."""
        self._recovery_callback = callback_fn

    @property
    def _reconnect_in_flight(self) -> bool:
        """Return if a login attempt is running."""
        return self._reconnect_task is not None and not self._reconnect_task.done()

    @callback
    def report_failure(
        self, err: Exception | None = None, *, log: bool = False
    ) -> None:
        """Mark the shared session unavailable and schedule one retry."""
        if self._stopped or self._reauth_required:
            return
        if self._recovering:
            self._recovery_failed = True
            self._set_available(False)
            return
        if self._retry_handle is not None or self._reconnect_in_flight:
            return

        self._cancel_stable_timer()
        self._set_available(False)

        self._schedule_retry(log=log)
        if err is not None:
            LOGGER.debug("Schedule reconnect to UniFi Network '%s'", err)

    def _cancel_stable_timer(self) -> None:
        """Cancel the pending reset of the retry backoff."""
        if self._stable_handle is not None:
            self._stable_handle.cancel()
            self._stable_handle = None

    @callback
    def _async_connection_stable(self) -> None:
        """Reset the retry backoff once the connection has stayed up."""
        self._stable_handle = None
        self._attempt = 0

    def _schedule_retry(self, *, log: bool = False) -> None:
        """Schedule the next session login attempt."""
        delay = self._backoff.next_delay(self._attempt)
        self._attempt += 1
        self._retry_handle = self.hass.loop.call_later(
            delay, self._async_reconnect, log
        )

    @callback
    def _async_reconnect(self, log: bool = False) -> None:
        """Try to restore the API session."""
        self._retry_handle = None
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return

        async def _reconnect() -> None:
            if log:
                LOGGER.info("Will try to reconnect to UniFi Network")
            try:
                async with asyncio.timeout(5):
                    await self.api.login()
            except aiounifi.LoginRequired, aiounifi.Unauthorized:
                self._reconnect_task = None
                self._reauth_required = True
                self.config_entry.async_start_reauth(self.hass)
                return
            except (TimeoutError, aiounifi.AiounifiException) as err:
                self._retry_after_failure(err)
                return

            try:
                async with asyncio.timeout(5):
                    await self.api.system_information.update()
            except (TimeoutError, aiounifi.AiounifiException) as err:
                self._retry_after_failure(err)
                return

            self._recovering = True
            self._recovery_failed = False
            self._set_available(True)
            try:
                if self._recovery_callback is not None:
                    await self._recovery_callback()
            finally:
                self._recovering = False
                self._reconnect_task = None

            if self._recovery_failed:
                self._cancel_stable_timer()
                self._schedule_retry()
            elif not self._stopped:
                self._stable_handle = self.hass.loop.call_later(
                    CONNECTION_STABLE_PERIOD, self._async_connection_stable
                )

        self._reconnect_task = self.hass.async_create_task(_reconnect())

    def _retry_after_failure(self, err: Exception) -> None:
        """Schedule another attempt after login or the readiness probe failed."""
        self._reconnect_task = None
        LOGGER.debug("UniFi Network is not ready after login: %s", err)
        self._schedule_retry()

    @callback
    def _set_available(self, available: bool) -> None:
        """Update shared session availability and signal entities."""
        if self.available == available:
            return
        self.available = available
        async_dispatcher_send(self.hass, self.signal)
        if available:
            LOGGER.info("Connection to UniFi Network restored")
        else:
            LOGGER.warning("Connection to UniFi Network lost")

    @callback
    def stop(self) -> None:
        """Cancel pending reconnect work."""
        self._stopped = True
        self._cancel_stable_timer()
        if self._retry_handle is not None:
            self._retry_handle.cancel()
            self._retry_handle = None
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        self._recovery_callback = None

    async def stop_and_wait(self) -> None:
        """Cancel and await an in-flight login attempt."""
        task = self._reconnect_task
        self.stop()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
