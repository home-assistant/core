"""DataUpdateCoordinator for the Verisure integration."""

import asyncio
from datetime import datetime, timedelta
from time import sleep
from typing import override

from verisure import (
    AuthenticationError as VerisureAuthenticationError,
    CookieReadError as VerisureCookieReadError,
    Error as VerisureError,
    LoginError as VerisureLoginError,
    RateLimitError as VerisureRateLimitError,
    RequestError as VerisureRequestError,
    ResponseError as VerisureResponseError,
    Session as Verisure,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle, dt as dt_util

from .const import (
    CONF_GIID,
    COOKIE_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DRY_RUN_FALLBACK_INTERVAL,
    LOGGER,
    RATE_LIMIT_BACKOFF,
)

type VerisureConfigEntry = ConfigEntry[VerisureDataUpdateCoordinator]

_MFA_REQUIRED_MESSAGE = (
    "Multifactor authentication enabled, disable or create MFA cookie"
)


def _requires_mfa_reauth(exc: VerisureLoginError) -> bool:
    """Return True when password login cannot proceed without MFA."""
    return _MFA_REQUIRED_MESSAGE in str(exc)


def _safe_nested_get(data: object, *keys: str) -> object:
    """Traverse nested dict keys, tolerating a missing or null value at any level.

    A plain chain of dict.get(key, {}) calls only falls back to {} when a key
    is absent; a GraphQL error response can return an explicit null instead
    (for example data itself, on an HTTP-200 error payload), which a chained
    .get() then raises AttributeError on.
    """
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


class VerisureDataUpdateCoordinator(DataUpdateCoordinator):
    """A Verisure Data Update Coordinator."""

    config_entry: VerisureConfigEntry

    def __init__(self, hass: HomeAssistant, entry: VerisureConfigEntry) -> None:
        """Initialize the Verisure hub."""
        self.imageseries: list[dict[str, str]] = []
        self._overview: list[dict] = []
        self._rate_limit_backoff_level = 0
        self._last_successful_cookie_refresh: datetime | None = None
        self._last_dry_run_check: datetime | None = None
        self._last_door_window_fingerprint: frozenset[tuple[str, str]] | None = None
        self._force_arm_required: bool | None = None
        self._dry_run_retry_after: datetime | None = None
        self._dry_run_backoff_level = 0

        self.verisure = Verisure(
            username=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            cookie_file_name=hass.config.path(
                STORAGE_DIR, f"verisure_{entry.data[CONF_EMAIL]}"
            ),
        )

        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_password_login_after_cookie_read(self) -> None:
        """Re-authenticate with password when the cookie file cannot be used."""
        try:
            await self.hass.async_add_executor_job(self.verisure.login)
        except VerisureAuthenticationError as login_ex:
            raise ConfigEntryAuthFailed(
                "Verisure re-authentication failed after cookie could not be read"
            ) from login_ex
        except VerisureRateLimitError as login_ex:
            self._raise_rate_limited(login_ex, "password login")
        except (VerisureRequestError, VerisureResponseError) as login_ex:
            raise UpdateFailed(
                "Could not refresh Verisure session (transient)"
            ) from login_ex
        except VerisureLoginError as login_ex:
            if _requires_mfa_reauth(login_ex):
                raise ConfigEntryAuthFailed(
                    "Verisure multifactor authentication required"
                ) from login_ex
            raise ConfigEntryAuthFailed(
                "Verisure re-authentication failed after cookie could not be read"
            ) from login_ex
        except VerisureError as login_ex:
            raise ConfigEntryAuthFailed(
                "Verisure re-authentication failed after cookie could not be read"
            ) from login_ex

    async def _async_refresh_session_after_auth_failure(self) -> None:
        """Recover session when cookie refresh indicates expired authentication."""
        try:
            await self.hass.async_add_executor_job(self.verisure.login_cookie)
        except VerisureAuthenticationError as ex:
            raise ConfigEntryAuthFailed(
                "Verisure authentication rejected (invalid or expired session)"
            ) from ex
        except VerisureCookieReadError:
            await self._async_password_login_after_cookie_read()
        except VerisureLoginError as ex:
            raise ConfigEntryAuthFailed("Credentials expired for Verisure") from ex
        except VerisureRateLimitError as ex:
            self._raise_rate_limited(ex, "session refresh")
        except (VerisureRequestError, VerisureResponseError) as ex:
            raise UpdateFailed("Could not refresh Verisure session (transient)") from ex
        except VerisureError as ex:
            raise UpdateFailed("Could not log in to Verisure") from ex

    def _rate_limit_retry_seconds(self) -> float:
        """Return the next retry delay and advance the backoff level."""
        level = min(self._rate_limit_backoff_level, len(RATE_LIMIT_BACKOFF) - 1)
        retry_after = RATE_LIMIT_BACKOFF[level].total_seconds()
        if self._rate_limit_backoff_level < len(RATE_LIMIT_BACKOFF) - 1:
            self._rate_limit_backoff_level += 1
        return retry_after

    def _raise_rate_limited(self, exc: VerisureRateLimitError, context: str) -> None:
        """Log rate limiting and defer the next poll."""
        retry_after = self._rate_limit_retry_seconds()
        LOGGER.warning(
            "Verisure rate limited during %s, %s; backing off %s seconds",
            context,
            exc,
            int(retry_after),
        )
        raise UpdateFailed(
            f"Verisure rate limited during {context}",
            retry_after=retry_after,
        ) from exc

    async def _async_refresh_cookie_if_needed(self) -> None:
        """Refresh the session cookie when it is close to expiring."""
        if (
            self._last_successful_cookie_refresh is not None
            and dt_util.utcnow() - self._last_successful_cookie_refresh
            < COOKIE_REFRESH_INTERVAL
        ):
            return

        try:
            await self.hass.async_add_executor_job(self.verisure.update_cookie)
        except VerisureAuthenticationError:
            LOGGER.debug("Cookie expired, acquiring new cookies")
            await self._async_refresh_session_after_auth_failure()
        except VerisureCookieReadError:
            LOGGER.debug("Cookie unreadable, re-authenticating with password")
            await self._async_password_login_after_cookie_read()
        except VerisureLoginError:
            LOGGER.debug("Login token expired, refreshing session")
            await self._async_refresh_session_after_auth_failure()
        except VerisureRateLimitError as ex:
            self._raise_rate_limited(ex, "cookie refresh")
        except (VerisureRequestError, VerisureResponseError) as ex:
            LOGGER.warning(
                "Verisure unreachable or server error during cookie refresh, %s", ex
            )
            raise UpdateFailed("Unable to update cookie - Verisure unreachable") from ex
        except VerisureError as ex:
            raise UpdateFailed("Unable to update cookie") from ex

        self._last_successful_cookie_refresh = dt_util.utcnow()

    async def _async_check_force_arm_required(self, door_window: dict) -> None:
        """Check via an arm state dry run whether arming currently requires force.

        Runs when a door/window state changes, readiness is not currently
        known, or otherwise at most once per DRY_RUN_FALLBACK_INTERVAL as a
        safety net for violation types not reflected in door/window state,
        for example an offline or otherwise faulted device. Checking on
        unknown readiness (rather than only a fingerprint change or the
        fallback interval) matters because the fingerprint is only stored on
        success: if a check fails and the door/window state then reverts to
        a value already seen before that failure, the fingerprint alone
        would look unchanged and silently skip the retry a failure is
        supposed to get on the next cycle. Failures are logged and do not
        fail the overall coordinator update; readiness stays unknown until a
        check succeeds (or after the rate limit backoff, if rate limited).
        """
        fingerprint = frozenset(
            (label, device.get("state")) for label, device in door_window.items()
        )
        fingerprint_changed = fingerprint != self._last_door_window_fingerprint
        due_for_fallback_check = (
            self._last_dry_run_check is None
            or dt_util.utcnow() - self._last_dry_run_check >= DRY_RUN_FALLBACK_INTERVAL
        )
        if (
            not fingerprint_changed
            and not due_for_fallback_check
            and self._force_arm_required is not None
        ):
            return
        if (
            self._dry_run_retry_after is not None
            and dt_util.utcnow() < self._dry_run_retry_after
        ):
            return

        # A due check is about to run; any failure below now leaves readiness
        # as unknown instead of holding onto a value that may no longer be
        # accurate, for example after a door/window change.
        self._force_arm_required = None

        try:
            dry_run = await self.hass.async_add_executor_job(
                self.verisure.request, self.verisure.arm_state_dry_run()
            )
        except VerisureRateLimitError as ex:
            self._defer_dry_run_retry(f"rate limited starting the dry run, {ex}")
            return
        except VerisureError as ex:
            LOGGER.debug("Could not start arm state dry run, %s", ex)
            return

        if not isinstance(dry_run, dict):
            return
        data = dry_run.get("data")
        if not isinstance(data, dict):
            return
        transaction_id = data.get("armStateDryRun")
        if not transaction_id:
            return

        result = None
        attempts = 0
        while result is None:
            if attempts == 30:
                break
            if attempts > 1:
                await asyncio.sleep(0.5)
            attempts += 1
            try:
                status = await self.hass.async_add_executor_job(
                    self.verisure.request,
                    self.verisure.arm_state_dry_run_status(transaction_id),
                )
            except VerisureRateLimitError as ex:
                self._defer_dry_run_retry(f"rate limited polling the dry run, {ex}")
                return
            except VerisureError as ex:
                LOGGER.debug("Could not poll arm state dry run, %s", ex)
                return
            if not isinstance(status, dict):
                return
            dry_run_status = _safe_nested_get(
                status, "data", "installation", "armState", "dryRunStatus"
            )
            if not isinstance(dry_run_status, dict):
                return
            if _safe_nested_get(dry_run_status, "status", "status") != "DONE":
                continue
            result = dry_run_status.get("result")
            if not isinstance(result, dict) or not isinstance(
                result.get("deviceViolations"), list
            ):
                LOGGER.debug("Arm state dry run completed without a violations list")
                return

        if result is None:
            self._defer_dry_run_retry(
                f"exhausted {attempts} poll attempts without a DONE status"
            )
            return

        self._force_arm_required = bool(result["deviceViolations"])
        self._last_dry_run_check = dt_util.utcnow()
        self._last_door_window_fingerprint = fingerprint
        self._dry_run_retry_after = None
        self._dry_run_backoff_level = 0

    def _defer_dry_run_retry(self, reason: str) -> None:
        """Back off the next dry run attempt on its own schedule.

        Used both for rate limits and for a transaction that never reaches a
        DONE status: either way, retrying right away risks piling more load
        onto a backend that is already struggling. Uses a dedicated counter
        and deadline rather than the coordinator's shared rate-limit backoff:
        that level is reset whenever the overall update succeeds, which
        happens right after this check runs on every cycle, so it can never
        actually defer a retry here. A dedicated deadline is also checked
        unconditionally, so it still defers a changed-fingerprint recheck,
        which would otherwise see the fingerprint as still changed (it is
        only stored on success) and retry every cycle.
        """
        level = min(self._dry_run_backoff_level, len(RATE_LIMIT_BACKOFF) - 1)
        self._dry_run_retry_after = dt_util.utcnow() + RATE_LIMIT_BACKOFF[level]
        if self._dry_run_backoff_level < len(RATE_LIMIT_BACKOFF) - 1:
            self._dry_run_backoff_level += 1
        LOGGER.debug(
            "Deferring next arm state dry run check until %s, %s",
            self._dry_run_retry_after,
            reason,
        )

    async def async_login(self) -> bool:
        """Login to Verisure."""
        try:
            await self.hass.async_add_executor_job(self.verisure.login_cookie)
        except VerisureAuthenticationError as ex:
            raise ConfigEntryAuthFailed(
                "Verisure authentication rejected (invalid or expired session)"
            ) from ex
        except VerisureCookieReadError:
            try:
                await self._async_password_login_after_cookie_read()
            except UpdateFailed as ex:
                LOGGER.warning(
                    "Verisure login unavailable (likely transient), %s",
                    ex,
                )
                return False
        except VerisureLoginError as ex:
            LOGGER.error("Credentials expired for Verisure, %s", ex)
            raise ConfigEntryAuthFailed("Credentials expired for Verisure") from ex
        except (
            VerisureRequestError,
            VerisureResponseError,
            VerisureRateLimitError,
        ) as ex:
            LOGGER.warning(
                "Verisure login unavailable (likely transient), %s",
                ex,
            )
            return False
        except VerisureError as ex:
            LOGGER.error("Could not log in to Verisure, %s", ex)
            return False

        await self.hass.async_add_executor_job(
            self.verisure.set_giid, self.config_entry.data[CONF_GIID]
        )

        return True

    @override
    async def _async_update_data(self) -> dict:
        """Fetch data from Verisure."""
        await self._async_refresh_cookie_if_needed()
        try:
            overview = await self.hass.async_add_executor_job(
                self.verisure.request,
                self.verisure.arm_state(),
                self.verisure.broadband(),
                self.verisure.cameras(),
                self.verisure.climate(),
                self.verisure.door_window(),
                self.verisure.smart_lock(),
                self.verisure.smartplugs(),
            )
        except VerisureError as err:
            LOGGER.error("Could not read overview, %s", err)
            raise UpdateFailed("Could not read overview") from err

        def unpack(overview: list, value: str) -> dict | list:
            unpacked: dict | list | None = next(
                (
                    item["data"]["installation"][value]
                    for item in overview
                    if value in item.get("data", {}).get("installation", {})
                ),
                None,
            )
            return unpacked or []

        door_window = {
            device["device"]["deviceLabel"]: device
            for device in unpack(overview, "doorWindows")
        }
        await self._async_check_force_arm_required(door_window)

        # Store data in a way Home Assistant can easily consume it
        self._overview = overview
        self._rate_limit_backoff_level = 0
        return {
            "alarm": unpack(overview, "armState"),
            "broadband": unpack(overview, "broadband"),
            "cameras": {
                device["device"]["deviceLabel"]: device
                for device in unpack(overview, "cameras")
            },
            "climate": {
                device["device"]["deviceLabel"]: device
                for device in unpack(overview, "climates")
            },
            "door_window": door_window,
            "locks": {
                device["device"]["deviceLabel"]: device
                for device in unpack(overview, "smartLocks")
            },
            "smart_plugs": {
                device["device"]["deviceLabel"]: device
                for device in unpack(overview, "smartplugs")
            },
            "force_arm_required": self._force_arm_required,
        }

    @Throttle(timedelta(seconds=60))
    def update_smartcam_imageseries(self) -> None:
        """Update the image series."""
        image_data = self.verisure.request(self.verisure.cameras_image_series())
        self.imageseries = [
            content
            for series in (
                image_data.get("data", {})
                .get("ContentProviderMediaSearch", {})
                .get("mediaSeriesList", [])
            )
            for content in series.get("deviceMediaList", [])
            if content.get("contentType") == "IMAGE_JPEG"
        ]

    @Throttle(timedelta(seconds=30))
    def smartcam_capture(self, device_id: str) -> None:
        """Capture a new image from a smartcam."""
        capture_request = self.verisure.request(
            self.verisure.camera_get_request_id(device_id)
        )
        request_id = (
            capture_request.get("data", {})
            .get("ContentProviderCaptureImageRequest", {})
            .get("requestId")
        )
        capture_status = None
        attempts = 0
        while capture_status != "AVAILABLE":
            if attempts == 30:
                break
            if attempts > 1:
                sleep(0.5)
            attempts += 1
            capture_data = self.verisure.request(
                self.verisure.camera_capture(device_id, request_id)
            )
            capture_status = (
                capture_data.get("data", {})
                .get("installation", {})
                .get("cameraContentProvider", {})
                .get("captureImageRequestStatus", {})
                .get("mediaRequestStatus")
            )
