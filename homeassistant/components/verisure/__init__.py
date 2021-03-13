"""Support for Verisure devices."""
from __future__ import annotations

import asyncio
import os
from typing import Any

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
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, ConfigEntry
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    ATTR_DEVICE_SERIAL,
    CONF_CODE_DIGITS,
    CONF_DEFAULT_LOCK_CODE,
    CONF_GIID,
    DOMAIN,
    LOGGER,
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
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Optional(CONF_CODE_DIGITS, default=4): cv.positive_int,
                    vol.Optional(CONF_GIID): cv.string,
                    vol.Optional(CONF_DEFAULT_LOCK_CODE): cv.string,
                },
                extra=vol.ALLOW_EXTRA,
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


DEVICE_SERIAL_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_SERIAL): cv.string})


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Verisure integration."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_EMAIL: config[DOMAIN][CONF_USERNAME],
                    CONF_PASSWORD: config[DOMAIN][CONF_PASSWORD],
                    CONF_GIID: config[DOMAIN].get(CONF_GIID),
                },
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Verisure from a config entry."""
    coordinator = VerisureDataUpdateCoordinator(hass, entry=entry)

    if not await coordinator.async_login():
        LOGGER.error("Login failed")
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH},
            data=entry.data,
        )
        return False

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, coordinator.async_logout)

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        LOGGER.error("Update failed")
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up all platforms for this device/entry.
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Verisure config entry."""
    unload_ok = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            )
        )
    )

    if unload_ok:
        cookie_file = hass.config.path(STORAGE_DIR, f"verisure_{entry.entry_id}")
        if os.path.exists(cookie_file):
            os.unlink(cookie_file)
        del hass.data[DOMAIN][entry.entry_id]

    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return unload_ok
