"""DataUpdateCoordinator for the Verisure integration."""

from __future__ import annotations

import asyncio
import re
from datetime import timedelta
from time import sleep

import requests.exceptions

from verisure import (
    Error as VerisureError,
    LoginError as VerisureLoginError,
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
from homeassistant.util import Throttle

from .const import CONF_GIID, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type VerisureConfigEntry = ConfigEntry["VerisureDataUpdateCoordinator"]

_COOKIE_REFRESH_ATTEMPTS = 3
_RETRY_DELAY_SEC = 1.0


def _verisure_message_signals_throttle(message: str) -> bool:
    """True when the API rejected the call for rate / quota limits (not invalid credentials)."""
    lower = message.lower()
    return (
        "aut_00021" in lower
        or "request limit" in lower
        or "rate limit" in lower
        or "too many requests" in lower
    )


def _is_transient_verisure_failure(exc: BaseException) -> bool:
    """True when the exception chain looks like network, 5xx, or local I/O — not bad password."""
    seen: set[int] = set()
    chain: BaseException | None = exc
    while chain is not None and id(chain) not in seen:
        seen.add(id(chain))
        if _verisure_message_signals_throttle(str(chain)):
            return True
        if isinstance(chain, (VerisureRequestError, VerisureResponseError)):
            return True
        if isinstance(chain, requests.exceptions.RequestException):
            return True
        if isinstance(chain, OSError):
            return True
        chain = chain.__cause__
    return False


def _verisure_response_http_status(exc: VerisureResponseError) -> int | None:
    """Return HTTP status from ResponseError when available."""
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    match = re.search(r"status code: (\d+)", str(exc))
    if match:
        return int(match.group(1))
    return None


class VerisureDataUpdateCoordinator(DataUpdateCoordinator):
    """A Verisure Data Update Coordinator."""

    config_entry: VerisureConfigEntry

    def __init__(self, hass: HomeAssistant, entry: VerisureConfigEntry) -> None:
        """Initialize the Verisure hub."""
        self.imageseries: list[dict[str, str]] = []
        self._overview: list[dict] = []

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

    async def async_login(self) -> bool:
        """Login to Verisure."""
        try:
            await self.hass.async_add_executor_job(self.verisure.login_cookie)
        except VerisureResponseError as ex:
            status = _verisure_response_http_status(ex)
            if status in (401, 403):
                raise ConfigEntryAuthFailed(
                    "Verisure authentication rejected (invalid or expired session)"
                ) from ex
            LOGGER.warning(
                "Verisure login unavailable (likely transient network or storage), %s",
                ex,
            )
            return False
        except VerisureLoginError as ex:
            if str(ex) == "Failed to read cookie":
                try:
                    await self.hass.async_add_executor_job(self.verisure.login)
                except VerisureError as login_ex:
                    if isinstance(login_ex, VerisureResponseError):
                        status = _verisure_response_http_status(login_ex)
                        if status in (401, 403):
                            raise ConfigEntryAuthFailed(
                                "Verisure re-authentication failed after cookie could not be read"
                            ) from login_ex
                    if _is_transient_verisure_failure(login_ex):
                        LOGGER.warning(
                            "Verisure login unavailable (likely transient network or storage), %s",
                            login_ex,
                        )
                        return False
                    raise ConfigEntryAuthFailed(
                        "Verisure re-authentication failed after cookie could not be read"
                    ) from login_ex
            elif _is_transient_verisure_failure(ex):
                LOGGER.warning(
                    "Verisure login unavailable (likely transient network or storage), %s",
                    ex,
                )
                return False
            else:
                LOGGER.error("Credentials expired for Verisure, %s", ex)
                raise ConfigEntryAuthFailed("Credentials expired for Verisure") from ex
        except VerisureError as ex:
            LOGGER.error("Could not log in to verisure, %s", ex)
            return False

        await self.hass.async_add_executor_job(
            self.verisure.set_giid, self.config_entry.data[CONF_GIID]
        )

        return True

    async def _async_update_data(self) -> dict:
        """Fetch data from Verisure."""
        last_login_error: VerisureLoginError | None = None
        cookie_refreshed = False
        for attempt in range(_COOKIE_REFRESH_ATTEMPTS):
            try:
                await self.hass.async_add_executor_job(self.verisure.update_cookie)
                cookie_refreshed = True
                break
            except (VerisureRequestError, VerisureResponseError) as ex:
                LOGGER.warning(
                    "Verisure unreachable or server error during cookie refresh, %s", ex
                )
                raise UpdateFailed("Unable to update cookie — Verisure unreachable") from ex
            except VerisureLoginError as ex:
                last_login_error = ex
                if attempt + 1 < _COOKIE_REFRESH_ATTEMPTS:
                    LOGGER.debug(
                        "Cookie refresh login error attempt %s, retrying: %s",
                        attempt + 1,
                        ex,
                    )
                    await asyncio.sleep(_RETRY_DELAY_SEC)
                    continue

        if not cookie_refreshed:
            assert last_login_error is not None
            LOGGER.debug("Cookie expired, acquiring new cookies")
            try:
                await self.hass.async_add_executor_job(self.verisure.login_cookie)
            except VerisureResponseError as ex:
                status = _verisure_response_http_status(ex)
                if status in (401, 403):
                    raise ConfigEntryAuthFailed(
                        "Verisure authentication rejected (invalid or expired session)"
                    ) from ex
                LOGGER.warning(
                    "Verisure login unavailable (likely transient network or storage), %s",
                    ex,
                )
                raise UpdateFailed(
                    "Could not refresh Verisure session (transient)"
                ) from ex
            except VerisureLoginError as ex:
                if str(ex) == "Failed to read cookie":
                    try:
                        await self.hass.async_add_executor_job(self.verisure.login)
                    except VerisureError as login_ex:
                        if isinstance(login_ex, VerisureResponseError):
                            status = _verisure_response_http_status(login_ex)
                            if status in (401, 403):
                                raise ConfigEntryAuthFailed(
                                    "Verisure re-authentication failed after cookie could not be read"
                                ) from login_ex
                        if _is_transient_verisure_failure(login_ex):
                            LOGGER.warning(
                                "Verisure login unavailable (likely transient network or storage), %s",
                                login_ex,
                            )
                            raise UpdateFailed(
                                "Could not refresh Verisure session (transient)"
                            ) from login_ex
                        raise ConfigEntryAuthFailed(
                            "Verisure re-authentication failed after cookie could not be read"
                        ) from login_ex
                elif _is_transient_verisure_failure(ex):
                    LOGGER.warning(
                        "Verisure session refresh failed (transient), %s",
                        ex,
                    )
                    raise UpdateFailed(
                        "Could not refresh Verisure session (transient)"
                    ) from ex
                else:
                    LOGGER.error("Credentials expired for Verisure, %s", ex)
                    raise ConfigEntryAuthFailed(
                        "Credentials expired for Verisure"
                    ) from ex
            except VerisureError as ex:
                LOGGER.error("Could not log in to verisure, %s", ex)
                raise UpdateFailed("Could not log in to verisure") from ex
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

        # Store data in a way Home Assistant can easily consume it
        self._overview = overview
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
            "door_window": {
                device["device"]["deviceLabel"]: device
                for device in unpack(overview, "doorWindows")
            },
            "locks": {
                device["device"]["deviceLabel"]: device
                for device in unpack(overview, "smartLocks")
            },
            "smart_plugs": {
                device["device"]["deviceLabel"]: device
                for device in unpack(overview, "smartplugs")
            },
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
