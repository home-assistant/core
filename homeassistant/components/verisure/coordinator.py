"""DataUpdateCoordinator for the Verisure integration."""
from __future__ import annotations

from datetime import timedelta
from time import sleep

from verisure import (
    Error as VerisureError,
    LoginError as VerisureLoginError,
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


class VerisureDataUpdateCoordinator(DataUpdateCoordinator):
    """A Verisure Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Verisure hub."""
        self.imageseries: list[dict[str, str]] = []
        self.entry = entry
        self._overview: list[dict] = []

        self.verisure = Verisure(
            username=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            cookie_file_name=hass.config.path(
                STORAGE_DIR, f"verisure_{entry.data[CONF_EMAIL]}"
            ),
        )

        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def async_login(self) -> bool:
        """Login to Verisure."""
        try:
            await self.hass.async_add_executor_job(self.verisure.login_cookie)
        except VerisureLoginError as ex:
            LOGGER.error("Credentials expired for Verisure, %s", ex)
            raise ConfigEntryAuthFailed("Credentials expired for Verisure") from ex
        except VerisureError as ex:
            LOGGER.error("Could not log in to verisure, %s", ex)
            return False

        await self.hass.async_add_executor_job(
            self.verisure.set_giid, self.entry.data[CONF_GIID]
        )

        return True

    async def _async_update_data(self) -> dict:
        """Fetch data from Verisure."""
        try:
            await self.hass.async_add_executor_job(self.verisure.update_cookie)
        except VerisureLoginError:
            try:
                await self.hass.async_add_executor_job(self.verisure.login_cookie)
            except VerisureLoginError as ex:
                LOGGER.error("Credentials expired for Verisure, %s", ex)
                raise ConfigEntryAuthFailed("Credentials expired for Verisure") from ex
            except VerisureError as ex:
                LOGGER.error("Could not log in to verisure, %s", ex)
                raise ConfigEntryAuthFailed("Could not log in to verisure") from ex
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
