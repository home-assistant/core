"""DataUpdateCoordinator for the Verisure integration."""
from __future__ import annotations

from datetime import timedelta

from verisure import (
    Error as VerisureError,
    ResponseError as VerisureResponseError,
    Session as Verisure,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, HTTP_SERVICE_UNAVAILABLE
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import Throttle

from .const import CONF_GIID, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


class VerisureDataUpdateCoordinator(DataUpdateCoordinator):
    """A Verisure Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Verisure hub."""
        self.imageseries = {}
        self.entry = entry

        self.verisure = Verisure(
            username=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            cookieFileName=hass.config.path(STORAGE_DIR, f"verisure_{entry.entry_id}"),
        )

        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def async_login(self) -> bool:
        """Login to Verisure."""
        try:
            await self.hass.async_add_executor_job(self.verisure.login)
        except VerisureError as ex:
            LOGGER.error("Could not log in to verisure, %s", ex)
            return False

        await self.hass.async_add_executor_job(
            self.verisure.set_giid, self.entry.data[CONF_GIID]
        )

        return True

    async def async_logout(self, _event: Event) -> bool:
        """Logout from Verisure."""
        try:
            await self.hass.async_add_executor_job(self.verisure.logout)
        except VerisureError as ex:
            LOGGER.error("Could not log out from verisure, %s", ex)
            return False
        return True

    async def _async_update_data(self) -> dict:
        """Fetch data from Verisure."""
        try:
            overview = await self.hass.async_add_executor_job(
                self.verisure.get_overview
            )
        except VerisureResponseError as ex:
            LOGGER.error("Could not read overview, %s", ex)
            if ex.status_code == HTTP_SERVICE_UNAVAILABLE:  # Service unavailable
                LOGGER.info("Trying to log in again")
                await self.async_login()
                return {}
            raise

        # Store data in a way Home Assistant can easily consume it
        return {
            "alarm": overview["armState"],
            "ethernet": overview.get("ethernetConnectedNow"),
            "cameras": {
                device["deviceLabel"]: device
                for device in overview["customerImageCameras"]
            },
            "climate": {
                device["deviceLabel"]: device for device in overview["climateValues"]
            },
            "door_window": {
                device["deviceLabel"]: device
                for device in overview["doorWindow"]["doorWindowDevice"]
            },
            "locks": {
                device["deviceLabel"]: device
                for device in overview["doorLockStatusList"]
            },
            "mice": {
                device["deviceLabel"]: device
                for device in overview["eventCounts"]
                if device["deviceType"] == "MOUSE1"
            },
            "smart_plugs": {
                device["deviceLabel"]: device for device in overview["smartPlugs"]
            },
        }

    @Throttle(timedelta(seconds=60))
    def update_smartcam_imageseries(self) -> None:
        """Update the image series."""
        self.imageseries = self.verisure.get_camera_imageseries()

    @Throttle(timedelta(seconds=30))
    def smartcam_capture(self, device_id: str) -> None:
        """Capture a new image from a smartcam."""
        self.verisure.capture_image(device_id)
