"""DataUpdateCoordinator for the Verisure integration."""

from datetime import timedelta
from time import sleep

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
from homeassistant.util import Throttle

from .const import CONF_GIID, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type VerisureConfigEntry = ConfigEntry[VerisureDataUpdateCoordinator]

_MFA_REQUIRED_MESSAGE = (
    "Multifactor authentication enabled, disable or create MFA cookie"
)


def _requires_mfa_reauth(exc: VerisureLoginError) -> bool:
    """Return True when password login cannot proceed without MFA."""
    return _MFA_REQUIRED_MESSAGE in str(exc)


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

    async def _async_password_login_after_cookie_read(self) -> None:
        """Re-authenticate with password when the cookie file cannot be used."""
        try:
            await self.hass.async_add_executor_job(self.verisure.login)
        except VerisureAuthenticationError as login_ex:
            raise ConfigEntryAuthFailed(
                "Verisure re-authentication failed after cookie could not be read"
            ) from login_ex
        except (
            VerisureRequestError,
            VerisureResponseError,
            VerisureRateLimitError,
        ) as login_ex:
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
        except (
            VerisureRequestError,
            VerisureResponseError,
            VerisureRateLimitError,
        ) as ex:
            raise UpdateFailed("Could not refresh Verisure session (transient)") from ex
        except VerisureError as ex:
            raise UpdateFailed("Could not log in to Verisure") from ex

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

    async def _async_update_data(self) -> dict:
        """Fetch data from Verisure."""
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
            LOGGER.warning("Verisure rate limited during cookie refresh, %s", ex)
            raise UpdateFailed(
                "Unable to update cookie - Verisure rate limited"
            ) from ex
        except (VerisureRequestError, VerisureResponseError) as ex:
            LOGGER.warning(
                "Verisure unreachable or server error during cookie refresh, %s", ex
            )
            raise UpdateFailed("Unable to update cookie - Verisure unreachable") from ex
        except VerisureError as ex:
            raise UpdateFailed("Unable to update cookie") from ex
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
