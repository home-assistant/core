"""Support for Verisure devices."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Literal

from jsonpath import jsonpath
from verisure import (
    Error as VerisureError,
    ResponseError as VerisureResponseError,
    Session as Verisure,
)
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    HTTP_SERVICE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import Throttle

from .const import (
    ATTR_DEVICE_SERIAL,
    CONF_ALARM,
    CONF_CODE_DIGITS,
    CONF_DEFAULT_LOCK_CODE,
    CONF_DOOR_WINDOW,
    CONF_GIID,
    CONF_HYDROMETERS,
    CONF_LOCKS,
    CONF_MOUSE,
    CONF_SMARTCAM,
    CONF_SMARTPLUGS,
    CONF_THERMOMETERS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MIN_SCAN_INTERVAL,
    SERVICE_CAPTURE_SMARTCAM,
    SERVICE_DISABLE_AUTOLOCK,
    SERVICE_ENABLE_AUTOLOCK,
)

PLATFORMS = [
    "sensor",
    "switch",
    "alarm_control_panel",
    "lock",
    "camera",
    "binary_sensor",
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Optional(CONF_ALARM, default=True): cv.boolean,
                vol.Optional(CONF_CODE_DIGITS, default=4): cv.positive_int,
                vol.Optional(CONF_DOOR_WINDOW, default=True): cv.boolean,
                vol.Optional(CONF_GIID): cv.string,
                vol.Optional(CONF_HYDROMETERS, default=True): cv.boolean,
                vol.Optional(CONF_LOCKS, default=True): cv.boolean,
                vol.Optional(CONF_DEFAULT_LOCK_CODE): cv.string,
                vol.Optional(CONF_MOUSE, default=True): cv.boolean,
                vol.Optional(CONF_SMARTPLUGS, default=True): cv.boolean,
                vol.Optional(CONF_THERMOMETERS, default=True): cv.boolean,
                vol.Optional(CONF_SMARTCAM, default=True): cv.boolean,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): (
                    vol.All(cv.time_period, vol.Clamp(min=MIN_SCAN_INTERVAL))
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

DEVICE_SERIAL_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_SERIAL): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Verisure integration."""
    verisure = Verisure(config[DOMAIN][CONF_USERNAME], config[DOMAIN][CONF_PASSWORD])
    coordinator = VerisureDataUpdateCoordinator(
        hass, session=verisure, domain_config=config[DOMAIN]
    )

    if not await hass.async_add_executor_job(coordinator.login):
        LOGGER.error("Login failed")
        return False

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, lambda event: coordinator.logout()
    )

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        LOGGER.error("Update failed")
        return False

    hass.data[DOMAIN] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(hass, platform, DOMAIN, {}, config)
        )

    async def capture_smartcam(service):
        """Capture a new picture from a smartcam."""
        device_id = service.data[ATTR_DEVICE_SERIAL]
        try:
            await hass.async_add_executor_job(coordinator.smartcam_capture, device_id)
            LOGGER.debug("Capturing new image from %s", ATTR_DEVICE_SERIAL)
        except VerisureError as ex:
            LOGGER.error("Could not capture image, %s", ex)

    hass.services.async_register(
        DOMAIN, SERVICE_CAPTURE_SMARTCAM, capture_smartcam, schema=DEVICE_SERIAL_SCHEMA
    )

    async def disable_autolock(service):
        """Disable autolock on a doorlock."""
        device_id = service.data[ATTR_DEVICE_SERIAL]
        try:
            await hass.async_add_executor_job(coordinator.disable_autolock, device_id)
            LOGGER.debug("Disabling autolock on%s", ATTR_DEVICE_SERIAL)
        except VerisureError as ex:
            LOGGER.error("Could not disable autolock, %s", ex)

    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE_AUTOLOCK, disable_autolock, schema=DEVICE_SERIAL_SCHEMA
    )

    async def enable_autolock(service):
        """Enable autolock on a doorlock."""
        device_id = service.data[ATTR_DEVICE_SERIAL]
        try:
            await hass.async_add_executor_job(coordinator.enable_autolock, device_id)
            LOGGER.debug("Enabling autolock on %s", ATTR_DEVICE_SERIAL)
        except VerisureError as ex:
            LOGGER.error("Could not enable autolock, %s", ex)

    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE_AUTOLOCK, enable_autolock, schema=DEVICE_SERIAL_SCHEMA
    )
    return True


class VerisureDataUpdateCoordinator(DataUpdateCoordinator):
    """A Verisure Data Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, domain_config: ConfigType, session: Verisure
    ) -> None:
        """Initialize the Verisure hub."""
        self.imageseries = {}
        self.config = domain_config
        self.giid = domain_config.get(CONF_GIID)

        self.session = session

        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=domain_config[CONF_SCAN_INTERVAL]
        )

    def login(self) -> bool:
        """Login to Verisure."""
        try:
            self.session.login()
        except VerisureError as ex:
            LOGGER.error("Could not log in to verisure, %s", ex)
            return False
        if self.giid:
            return self.set_giid()
        return True

    def logout(self) -> bool:
        """Logout from Verisure."""
        try:
            self.session.logout()
        except VerisureError as ex:
            LOGGER.error("Could not log out from verisure, %s", ex)
            return False
        return True

    def set_giid(self) -> bool:
        """Set installation GIID."""
        try:
            self.session.set_giid(self.giid)
        except VerisureError as ex:
            LOGGER.error("Could not set installation GIID, %s", ex)
            return False
        return True

    async def _async_update_data(self) -> dict:
        """Fetch data from Verisure."""
        try:
            return await self.hass.async_add_executor_job(self.session.get_overview)
        except VerisureResponseError as ex:
            LOGGER.error("Could not read overview, %s", ex)
            if ex.status_code == HTTP_SERVICE_UNAVAILABLE:  # Service unavailable
                LOGGER.info("Trying to log in again")
                await self.hass.async_add_executor_job(self.login)
                return {}
            raise

    @Throttle(timedelta(seconds=60))
    def update_smartcam_imageseries(self) -> None:
        """Update the image series."""
        self.imageseries = self.session.get_camera_imageseries()

    @Throttle(timedelta(seconds=30))
    def smartcam_capture(self, device_id: str) -> None:
        """Capture a new image from a smartcam."""
        self.session.capture_image(device_id)

    def disable_autolock(self, device_id: str) -> None:
        """Disable autolock."""
        self.session.set_lock_config(device_id, auto_lock_enabled=False)

    def enable_autolock(self, device_id: str) -> None:
        """Enable autolock."""
        self.session.set_lock_config(device_id, auto_lock_enabled=True)

    def get(self, jpath: str, *args) -> list[Any] | Literal[False]:
        """Get values from the overview that matches the jsonpath."""
        res = jsonpath(self.data, jpath % args)
        return res or []

    def get_first(self, jpath: str, *args) -> Any | None:
        """Get first value from the overview that matches the jsonpath."""
        res = self.get(jpath, *args)
        return res[0] if res else None

    def get_image_info(self, jpath: str, *args) -> list[Any] | Literal[False]:
        """Get values from the imageseries that matches the jsonpath."""
        res = jsonpath(self.imageseries, jpath % args)
        return res or []
