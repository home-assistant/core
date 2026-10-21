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
NOT_READY_ERRORS = (
    *APPLICATION_DOWN_ERRORS,
    aiounifi.LoginRequired,
    aiounifi.TwoFaTokenRequired,
    aiounifi.Unauthorized,
)
# Account settings changed, only the user can resolve it
ACCOUNT_ERRORS = (aiounifi.NoPermission, aiounifi.TwoFaTokenRequired)
# Rejected credentials, which a booting console can also answer for a moment.
# UniFi OS answers a wrong password with 403, but 401 when its login service
# is down, which aiounifi raises as LoginRequired.
LOGIN_REJECTED_ERRORS = (aiounifi.Forbidden, aiounifi.Unauthorized)
LOGIN_REJECTIONS_BEFORE_REAUTH = 3
# Only a login answers so, aiounifi logged in again on its own within a request
LOGIN_ONLY_ERRORS = (aiounifi.AuthenticationRateLimitError, aiounifi.TwoFaTokenRequired)
# Errors of a request the application answers, but also of the login aiounifi
# tries on its own when the session expired
UNCLEAR_SESSION_ERRORS = (
    aiounifi.Forbidden,
    aiounifi.NoPermission,
    aiounifi.ResponseError,
)


def retry_delay(attempt: int) -> float:
    """Return the jittered delay in seconds for a zero-based attempt number."""
    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
    return delay * random.uniform(1 - RETRY_JITTER, 1 + RETRY_JITTER)


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
        self._reconnect_task: asyncio.Task[None] | None = None
        self._verify_task: asyncio.Task[None] | None = None
        self._stable_handle: asyncio.TimerHandle | None = None
        self._recovering = False
        self._reauth_required = False
        self._stopped = False
        self._login_rejections = 0
        self._rate_limited = False
        self._rate_limit_pause = 0
        self._rate_limit_logged = False
        self._session_confirmed = False
        self._logged_error: type[BaseException] | None = None

    @property
    def _reconnect_in_flight(self) -> bool:
        """Return if a reconnect attempt checks the session or logs in.

        The resync phase does not count, a failure there must mark the hub down.
        """
        return (
            not self._recovering
            and self._reconnect_task is not None
            and not self._reconnect_task.done()
        )

    @callback
    def report_failure(self, err: Exception | None = None) -> None:
        """Mark the shared session unavailable and schedule one retry."""
        if not self._reauth_required:
            self._session_lost(err)

    def _session_lost(self, err: Exception | None) -> None:
        """Mark the session unavailable, also when reauth just started."""
        if self._stopped:
            return
        if self._retry_handle is not None or self._reconnect_in_flight:
            return

        self._session_confirmed = False
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
        LOGGER.debug("Checking UniFi Network session, request failed with '%s'", err)
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
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await self.api.system_information.update()
        except LOGIN_ONLY_ERRORS as probe_err:
            self._handle_login_error(probe_err)
            self._session_lost(probe_err)
        except NOT_READY_ERRORS as probe_err:
            self.report_failure(probe_err)
        except UNCLEAR_SESSION_ERRORS as probe_err:
            if self._session_confirmed:
                # Once aiounifi failed to log in on its own, its next requests
                # raise LoginRequired, so one login per session is enough
                LOGGER.debug("UniFi Network answered with '%s'", probe_err)
                return
            LOGGER.debug("Logging in to check the session: %r", probe_err)
            if not await self._async_login(
                follows_rejection=isinstance(probe_err, LOGIN_REJECTED_ERRORS)
            ):
                self._session_lost(probe_err)
                return
            self._session_confirmed = True
            if not await self._async_application_ready():
                self.report_failure()
        except aiounifi.AiounifiException as probe_err:
            LOGGER.debug("UniFi Network answered with '%s'", probe_err)

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
        """Schedule the next reconnect attempt unless one is pending."""
        if self._stopped or self._retry_handle is not None:
            return
        if self._rate_limited:
            self._rate_limited = False
            delay: float = self._rate_limit_pause
            if self._reauth_required:
                delay = max(delay, REAUTH_RETRY_INTERVAL)
        elif self._reauth_required:
            delay = REAUTH_RETRY_INTERVAL
        else:
            delay = retry_delay(self._attempt)
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
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await self.api.system_information.update()
        except APPLICATION_DOWN_ERRORS as err:
            LOGGER.debug("UniFi Network is not ready: %r", err)
            return
        except LOGIN_ONLY_ERRORS as err:
            self._handle_login_error(err)
            return
        except aiounifi.AiounifiException as err:
            # An expired session, or an answer that can also come from the
            # login aiounifi tried on its own, a login tells them apart
            LOGGER.debug("UniFi Network did not accept the session: %r", err)
            if not await self._async_login(
                follows_rejection=isinstance(err, LOGIN_REJECTED_ERRORS)
            ):
                return
            if not await self._async_application_ready():
                return

        self._login_rejections = 0
        self._rate_limit_pause = 0
        self._rate_limit_logged = False
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

    async def _async_login(self, *, follows_rejection: bool = False) -> bool:
        """Log in, return if it worked."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await self.api.login()
        except (TimeoutError, aiounifi.AiounifiException) as err:
            self._handle_login_error(err, follows_rejection=follows_rejection)
            return False
        self._login_rejections = 0
        self._rate_limit_pause = 0
        return True

    def _handle_login_error(
        self, err: Exception, *, follows_rejection: bool = False
    ) -> None:
        """Count a failed login, start reauth or pause retries if needed.

        A login can follow one aiounifi tried on its own and that was rejected.
        """
        LOGGER.debug("UniFi Network login failed: %r", err)
        rate_limited = isinstance(err, aiounifi.AuthenticationRateLimitError)
        if rate_limited:
            self._rate_limited = True
            self._rate_limit_pause = min(
                2 * self._rate_limit_pause or RATE_LIMIT_PAUSE, MAX_RATE_LIMIT_PAUSE
            )
            if not self._rate_limit_logged:
                self._rate_limit_logged = True
                LOGGER.info(
                    "UniFi Network at %s limits logins, pausing reconnects for %s"
                    " seconds",
                    self.config_entry.data[CONF_HOST],
                    self._rate_limit_pause,
                )
        else:
            self._rate_limit_pause = 0

        if isinstance(err, ACCOUNT_ERRORS):
            self._start_reauth()
        elif isinstance(err, LOGIN_REJECTED_ERRORS) or (
            # Wrong passwords lock the login, the lock hides the next rejections
            rate_limited and (self._login_rejections or follows_rejection)
        ):
            # The login aiounifi tried before was rejected as well
            self._login_rejections += 2 if follows_rejection else 1
            if self._login_rejections >= LOGIN_REJECTIONS_BEFORE_REAUTH:
                self._start_reauth()
        elif not rate_limited:
            # Only rejections in a row start reauth
            self._login_rejections = 0

    async def _async_application_ready(self) -> bool:
        """Return if the Network application answers after a login."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await self.api.system_information.update()
        except LOGIN_ONLY_ERRORS as err:
            self._handle_login_error(err)
            return False
        except NOT_READY_ERRORS as err:
            LOGGER.debug("UniFi Network is not ready: %r", err)
            return False
        except aiounifi.AiounifiException as err:
            # The application answers, the account may not see system information
            LOGGER.debug("UniFi Network answered the readiness probe with: %s", err)
        return True

    def _start_reauth(self) -> None:
        """Ask the user to fix the login, keep retrying slowly meanwhile."""
        if self._reauth_required:
            return
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
