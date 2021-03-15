"""Support for Verisure devices."""
from __future__ import annotations

from verisure import Error as VerisureError
import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

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
from .coordinator import VerisureDataUpdateCoordinator

PLATFORMS = [
    ALARM_CONTROL_PANEL_DOMAIN,
    BINARY_SENSOR_DOMAIN,
    CAMERA_DOMAIN,
    LOCK_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
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
    coordinator = VerisureDataUpdateCoordinator(hass, config=config[DOMAIN])

    if not await coordinator.async_login():
        LOGGER.error("Login failed")
        return False

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, coordinator.async_logout)

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
