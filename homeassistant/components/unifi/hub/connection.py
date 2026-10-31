"""Manage the UniFi Network API session and reconnect policy."""

import asyncio
from collections.abc import Awaitable, Callable
import json
import random
from typing import TYPE_CHECKING

import aiounifi

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import LOGGER

if TYPE_CHECKING:
    from .. import UnifiConfigEntry

CONNECTION_STABLE_PERIOD = 60
REQUEST_TIMEOUT = 15
# A safety net, every refetch of the recovery has its own shorter timeout
RECOVERY_TIMEOUT = 60
# Retry delays grow per attempt, spread out so several entries don't retry in step
RETRY_DELAYS = (15, 30, 60)
RETRY_JITTER = 0.2
# UniFi OS limits logins per user and extends the lock on every attempt during
# it, so the pause doubles while logins stay limited
RATE_LIMIT_PAUSE = 300
MAX_RATE_LIMIT_PAUSE = 3600
# Keep trying slowly while reauth is pending, the login may work again on its own
REAUTH_RETRY_INTERVAL = 600

# The Network application is down or starting, a login would not help. A half
# started application can answer with invalid JSON.
APPLICATION_DOWN_ERRORS = (TimeoutError, json.JSONDecodeError, aiounifi.RequestError)
# The Network application is starting or the session expired, try again later
NOT_READY_ERRORS = (*APPLICATION_DOWN_ERRORS, aiounifi.LoginRequired)
# Account settings changed, only the user can resolve it
ACCOUNT_ERRORS = (aiounifi.TwoFaTokenRequired,)
# Rejected credentials or access, which a booting console can also answer for
# a moment. Every role with access to the Network application can read system
# information, and aiounifi raises these also when its own login was rejected.
# UniFi OS answers a wrong password with 403, but 401 when its login service
# is down, which aiounifi raises as LoginRequired.
LOGIN_REJECTED_ERRORS = (
    aiounifi.Forbidden,
    aiounifi.NoPermission,
    aiounifi.Unauthorized,
)
LOGIN_REJECTIONS_BEFORE_REAUTH = 3
# Answers of a login, a request raises them when aiounifi logged in on its own
LOGIN_ERRORS = (
    *ACCOUNT_ERRORS,
    *LOGIN_REJECTED_ERRORS,
    aiounifi.AuthenticationRateLimitError,
)
# Only a login answers these, so they need no further check
LOGIN_ONLY_ERRORS = (*ACCOUNT_ERRORS, aiounifi.AuthenticationRateLimitError)


def jitter(delay: float) -> float:
    """Spread a delay out so several entries don't retry in step."""
    return delay * random.uniform(1 - RETRY_JITTER, 1 + RETRY_JITTER)


def retry_delay(attempt: int) -> float:
    """Return the jittered delay in seconds for a zero-based attempt number."""
    return jitter(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])


class UnifiConnectionManager:
    """Own the API session state independently of its update transports."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: UnifiConfigEntry,
        api: aiounifi.Controller,
        signal: str,
        recovery_callback: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialize the manager.

        The recovery callback runs once the Network application is ready again.
        """
        self.hass = hass
        self.config_entry = config_entry
        self.api = api
        self.signal = signal
        self.available = True

        self._recovery_callback = recovery_callback
        self._attempt = 0
        self._retry_handle: asyncio.TimerHandle | None = None
        self._retry_for_reauth = False
        self._retry_for_rate_limit = False
        self._reconnect_task: asyncio.Task[None] | None = None
        self._verify_task: asyncio.Task[None] | None = None
        self._stable_handle: asyncio.TimerHandle | None = None
        self._recovering = False
        self._reauth_required = False
        self._stopped = False
        self._login_rejections = 0
        self._rate_limited = False
        self._rate_limit_pause = 0
        self._logged_error: type[BaseException] | None = None

    @callback
    def report_failure(self, err: Exception | None = None) -> None:
        """Mark the shared session unavailable and schedule one retry.

        A pending retry stays as it is unless a pause or reauth now needs a
        longer delay, and a running attempt schedules the next one itself if
        it ends unavailable.
        """
        if self._stopped:
            return

        self._cancel_stable_timer()
        self._set_available(False)

        self._schedule_retry()
        if err is not None:
            LOGGER.debug("Schedule reconnect to UniFi Network: %r", err)

    @callback
    def verify_session(self, err: Exception) -> None:
        """Check the session after a single request failed in transport.

        One endpoint can fail on its own, so only a failing readiness probe
        marks the whole session unavailable.
        """
        if self._stopped:
            return
        if isinstance(err, LOGIN_ONLY_ERRORS):
            # aiounifi logged in on its own, a probe would log in again. A
            # request from before an outage can answer late, its pause applies
            self._handle_login_error(err)
            self.report_failure(err)
            return
        # Reauth is only pending while the session is unavailable
        if not self.available:
            return
        if self._verify_task is not None and not self._verify_task.done():
            return
        self._verify_task = self.config_entry.async_create_background_task(
            self.hass, self._async_verify_session(err), "unifi_verify_session"
        )

    async def _async_verify_session(self, err: Exception) -> None:
        """Probe the Network application after a request failed."""
        LOGGER.debug("Checking UniFi Network session, request failed: %r", err)
        try:
            await self._async_check_session()
        except Exception as probe_err:  # noqa: BLE001
            # A broken probe must not take down a hub that still delivers data
            self._log_unexpected_error(
                "Unexpected error while checking UniFi Network", probe_err
            )

    async def _async_check_session(self) -> None:
        """Report a lost session unless the Network application answers it."""
        try:
            await self._async_probe()
        except LOGIN_ERRORS as probe_err:
            self._handle_login_error(probe_err)
            self.report_failure(probe_err)
        except NOT_READY_ERRORS as probe_err:
            self.report_failure(probe_err)
        except aiounifi.AiounifiException as probe_err:
            LOGGER.debug("UniFi Network answered the session check: %r", probe_err)

    async def _async_probe(self) -> None:
        """Request system information, which every account can read."""
        async with asyncio.timeout(REQUEST_TIMEOUT):
            await self.api.system_information.update()

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
        """Schedule the next reconnect attempt unless one is pending.

        A pending retry is pushed back when a pause or reauth started after it
        was scheduled, repeated failure reports leave it as it is.
        """
        if self._stopped:
            return
        remaining = 0.0
        rate_limit = self._retry_handle is not None and self._retry_for_rate_limit
        if self._retry_handle is not None:
            if not self._rate_limited and (
                not self._reauth_required or self._retry_for_reauth
            ):
                return
            remaining = self._retry_handle.when() - self.hass.loop.time()
            self._retry_handle.cancel()
        if self._rate_limited:
            self._rate_limited = False
            rate_limit = True
            delay = jitter(self._rate_limit_pause)
            if self._reauth_required:
                delay = max(delay, REAUTH_RETRY_INTERVAL)
        elif self._reauth_required:
            delay = REAUTH_RETRY_INTERVAL
        else:
            delay = retry_delay(self._attempt)
            self._attempt += 1
        self._retry_for_reauth = self._reauth_required
        self._retry_for_rate_limit = rate_limit
        self._retry_handle = self.hass.loop.call_later(
            max(delay, remaining), self._async_reconnect
        )

    @callback
    def _async_reconnect(self) -> None:
        """Try to restore the API session."""
        self._retry_handle = None
        if self._reconnect_task is not None and not self._reconnect_task.done():
            # The running attempt schedules the next one if it ends unavailable
            return
        if self._verify_task is not None and not self._verify_task.done():
            # The attempt checks the session itself, a late answer of an older
            # check must not mark it down again
            self._verify_task.cancel()

        self._reconnect_task = self.config_entry.async_create_background_task(
            self.hass, self._async_reconnect_and_recover(), "unifi_reconnect"
        )

    async def _async_reconnect_and_recover(self) -> None:
        """Check the session, log in if needed, and resync."""
        try:
            await self._async_try_reconnect()
        except Exception as err:  # noqa: BLE001
            self._log_unexpected_error(
                "Unexpected error while reconnecting to UniFi Network", err
            )
            self.report_failure(err)
        finally:
            self._recovering = False
            self._reconnect_task = None
            if not self.available:
                self._schedule_retry()

    async def _async_try_reconnect(self) -> None:
        """Run one session check, login if needed, and recovery attempt."""
        # The session can outlive an outage, only log in when it did not
        try:
            await self._async_probe()
        except APPLICATION_DOWN_ERRORS as err:
            LOGGER.debug("UniFi Network is not ready: %r", err)
            return
        except LOGIN_ERRORS as err:
            self._handle_login_error(err)
            return
        except aiounifi.AiounifiException as err:
            # An expired session, or an answer a fresh session tells apart
            LOGGER.debug("UniFi Network did not accept the session: %r", err)
            if not await self._async_login():
                return
            if not await self._async_application_ready():
                return

        self._login_rejections = 0
        self._rate_limited = False
        self._rate_limit_pause = 0
        if self._retry_handle is not None:
            # This attempt answers failures reported while it ran
            self._retry_handle.cancel()
            self._retry_handle = None
        if self._reauth_required:
            self._end_reauth()
        self._recovering = True
        self._set_available(True)
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

    async def _async_login(self) -> bool:
        """Log in, return if it worked."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await self.api.login()
        except Exception as err:
            self._handle_login_error(err)
            if not isinstance(err, (TimeoutError, aiounifi.AiounifiException)):
                raise
            return False
        self._login_rejections = 0
        self._rate_limit_pause = 0
        return True

    def _handle_login_error(self, err: Exception) -> None:
        """Count a failed login, start reauth or pause retries if needed."""
        LOGGER.debug("UniFi Network login failed: %r", err)
        if not isinstance(err, aiounifi.AuthenticationRateLimitError):
            self._rate_limit_pause = 0
            if isinstance(err, ACCOUNT_ERRORS):
                self._start_reauth()
            elif isinstance(err, LOGIN_REJECTED_ERRORS):
                self._count_rejection()
            else:
                # Only rejections in a row start reauth
                self._login_rejections = 0
            return

        if self._retry_handle is not None and self._retry_for_rate_limit:
            # Requests sent before the pause started answer late
            return
        if not self._rate_limit_pause:
            LOGGER.info(
                "UniFi Network at %s limits logins, pausing reconnects for %s seconds",
                self.config_entry.data[CONF_HOST],
                RATE_LIMIT_PAUSE,
            )
        elif self._login_rejections:
            # The limit of successful logins answers the same, only a lock that
            # outlasts a pause after rejections hides a wrong password
            self._count_rejection()
        self._rate_limited = True
        self._rate_limit_pause = min(
            2 * self._rate_limit_pause or RATE_LIMIT_PAUSE, MAX_RATE_LIMIT_PAUSE
        )

    def _count_rejection(self) -> None:
        """Start reauth after enough rejected logins in a row."""
        self._login_rejections += 1
        if self._login_rejections >= LOGIN_REJECTIONS_BEFORE_REAUTH:
            self._start_reauth()

    async def _async_application_ready(self) -> bool:
        """Return if the Network application answers after a login."""
        try:
            await self._async_probe()
        except LOGIN_ERRORS as err:
            # A fresh session that may not read the application lost its access
            self._handle_login_error(err)
            return False
        except NOT_READY_ERRORS as err:
            LOGGER.debug("UniFi Network is not ready: %r", err)
            return False
        except aiounifi.AiounifiException as err:
            # The application answers a fresh session
            LOGGER.debug("UniFi Network answered the readiness probe: %r", err)
        return True

    def _start_reauth(self) -> None:
        """Ask the user to fix the login, keep retrying slowly meanwhile."""
        self._reauth_required = True
        self.config_entry.async_start_reauth(self.hass)

    def _end_reauth(self) -> None:
        """Drop the reauth request once the login works again on its own."""
        self._reauth_required = False
        for flow in self.config_entry.async_get_active_flows(
            self.hass, {SOURCE_REAUTH}
        ):
            self.hass.config_entries.flow.async_abort(flow["flow_id"])

    def _log_unexpected_error(self, message: str, err: Exception) -> None:
        """Log a traceback once while the same error keeps repeating."""
        if type(err) is self._logged_error:
            LOGGER.debug(message, exc_info=err)
            return
        self._logged_error = type(err)
        LOGGER.error(message, exc_info=err)

    @callback
    def _set_available(self, available: bool) -> None:
        """Update shared session availability and signal entities."""
        if self.available == available:
            return
        self.available = available
        async_dispatcher_send(self.hass, self.signal)
        host = self.config_entry.data[CONF_HOST]
        if available:
            self._logged_error = None
            LOGGER.info("Connection to UniFi Network at %s restored", host)
        else:
            LOGGER.info("Connection to UniFi Network at %s lost", host)

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
