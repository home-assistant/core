"""Manage the UniFi Network API session and reconnect policy."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import random
from typing import TYPE_CHECKING

import aiounifi

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import LOGGER

if TYPE_CHECKING:
    from .. import UnifiConfigEntry

CONNECTION_STABLE_PERIOD = 60
REQUEST_TIMEOUT = 5
RECOVERY_TIMEOUT = 60

# The Network application is starting or the session expired, try again later.
# ValueError covers a half started application answering with invalid JSON.
NOT_READY_ERRORS = (
    TimeoutError,
    ValueError,
    aiounifi.LoginRequired,
    aiounifi.RequestError,
    aiounifi.TwoFaTokenRequired,
    aiounifi.Unauthorized,
)
# Credentials or account settings changed, only the user can resolve it
AUTH_ERRORS = (
    aiounifi.LoginRequired,
    aiounifi.NoPermission,
    aiounifi.TwoFaTokenRequired,
    aiounifi.Unauthorized,
)


@dataclass
class BackoffPolicy:
    """Exponential retry delay capped at a maximum interval."""

    base: float = 15
    factor: float = 2
    maximum: float = 60
    jitter: float = 0.2

    def next_delay(self, attempt: int) -> float:
        """Return the delay in seconds for a zero-based attempt number."""
        delay = self.base
        for _ in range(attempt):
            if delay >= self.maximum:
                return self.maximum
            delay *= self.factor
        return min(delay, self.maximum)

    def jittered_delay(self, attempt: int) -> float:
        """Return the delay spread out so several entries don't retry in step."""
        return self.next_delay(attempt) * random.uniform(
            1 - self.jitter, 1 + self.jitter
        )


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
        self._verify_task: asyncio.Task[None] | None = None
        self._stable_handle: asyncio.TimerHandle | None = None
        self._recovering = False
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
        return (
            not self._recovering
            and self._reconnect_task is not None
            and not self._reconnect_task.done()
        )

    @callback
    def report_failure(self, err: Exception | None = None) -> None:
        """Mark the shared session unavailable and schedule one retry."""
        if self._stopped or self._reauth_required:
            return
        if self._retry_handle is not None or self._reconnect_in_flight:
            return

        self._cancel_stable_timer()
        self._set_available(False)

        self._schedule_retry()
        if err is not None:
            LOGGER.debug("Schedule reconnect to UniFi Network '%s'", err)

    @callback
    def verify_session(self, err: Exception) -> None:
        """Check the session after a single request failed in transport.

        One endpoint can fail on its own, so only a failing readiness probe
        marks the whole session unavailable.
        """
        if not self.available or self._stopped or self._reauth_required:
            return
        if self._verify_task is not None and not self._verify_task.done():
            return
        self._verify_task = self.config_entry.async_create_background_task(
            self.hass, self._async_verify_session(err), "unifi_verify_session"
        )

    async def _async_verify_session(self, err: Exception) -> None:
        """Probe the Network application after a request failed."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await self.api.system_information.update()
        except NOT_READY_ERRORS as probe_err:
            self.report_failure(probe_err)
        except aiounifi.AiounifiException as probe_err:
            LOGGER.debug("UniFi Network answered with '%s'", probe_err)
        except Exception as probe_err:  # noqa: BLE001
            LOGGER.exception("Unexpected error while checking UniFi Network")
            self.report_failure(probe_err)
        else:
            LOGGER.debug("UniFi Network is reachable, request failed with '%s'", err)

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

    def _schedule_retry(self) -> None:
        """Schedule the next session login attempt unless one is pending."""
        if self._stopped or self._reauth_required or self._retry_handle is not None:
            return
        delay = self._backoff.jittered_delay(self._attempt)
        self._attempt += 1
        self._retry_handle = self.hass.loop.call_later(delay, self._async_reconnect)

    @callback
    def _async_reconnect(self) -> None:
        """Try to restore the API session."""
        self._retry_handle = None
        if self._reconnect_task is not None and not self._reconnect_task.done():
            # The running attempt schedules the next one if it ends unavailable
            return

        self._reconnect_task = self.config_entry.async_create_background_task(
            self.hass, self._async_reconnect_and_recover(), "unifi_reconnect"
        )

    async def _async_reconnect_and_recover(self) -> None:
        """Log in, wait for the Network application and resync."""
        try:
            await self._async_try_reconnect()
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected error while reconnecting to UniFi Network")
            self.report_failure(err)
        finally:
            self._recovering = False
            self._reconnect_task = None
            if not self.available:
                self._schedule_retry()

    async def _async_try_reconnect(self) -> None:
        """Run one login, readiness probe and recovery attempt."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await self.api.login()
        except AUTH_ERRORS as err:
            LOGGER.debug("UniFi Network rejected the login: %s", err)
            self._reauth_required = True
            self.config_entry.async_start_reauth(self.hass)
            return
        except (TimeoutError, aiounifi.AiounifiException) as err:
            LOGGER.debug("UniFi Network login failed: %s", err)
            return

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await self.api.system_information.update()
        except NOT_READY_ERRORS as err:
            LOGGER.debug("UniFi Network is not ready after login: %s", err)
            return
        except aiounifi.AiounifiException as err:
            # The application answers, the account may not see system information
            LOGGER.debug("UniFi Network answered the readiness probe with: %s", err)

        self._recovering = True
        self._set_available(True)
        if self._recovery_callback is not None:
            try:
                async with asyncio.timeout(RECOVERY_TIMEOUT):
                    await self._recovery_callback()
            except TimeoutError as err:
                self.report_failure(err)
                return

        if self.available and not self._stopped:
            self._stable_handle = self.hass.loop.call_later(
                CONNECTION_STABLE_PERIOD, self._async_connection_stable
            )

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
            LOGGER.info("Connection to UniFi Network lost")

    @callback
    def stop(self) -> None:
        """Cancel pending reconnect work."""
        self._stopped = True
        self._cancel_stable_timer()
        if self._retry_handle is not None:
            self._retry_handle.cancel()
            self._retry_handle = None
        for task in self._pending_tasks:
            task.cancel()
        self._reconnect_task = None
        self._verify_task = None
        self._recovery_callback = None

    async def stop_and_wait(self) -> None:
        """Cancel and await in-flight login and probe attempts."""
        tasks = self._pending_tasks
        self.stop()
        await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def _pending_tasks(self) -> list[asyncio.Task[None]]:
        """Return the login and probe tasks that are still referenced."""
        return [
            task
            for task in (self._reconnect_task, self._verify_task)
            if task is not None
        ]
