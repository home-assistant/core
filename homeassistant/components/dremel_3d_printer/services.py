"""Services for the Dremel 3D Printer integration."""
from __future__ import annotations

import os

from dremel3dpy import Dremel3DPrinter
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry

from .const import (
    _LOGGER,
    ATTR_DEVICE_ID,
    ATTR_FILEPATH,
    ATTR_URL,
    DOMAIN,
    EVENT_DATA_NEW_PRINT_STATS,
    SERVICE_PAUSE_JOB,
    SERVICE_PRINT_JOB,
    SERVICE_RESUME_JOB,
    SERVICE_STOP_JOB,
)

SERVICE_PRINT_JOB_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_FILEPATH): cv.string,
        vol.Optional(ATTR_URL): cv.string,
    }
)

SERVICE_COMMON_JOB_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)


def file_exists(hass: HomeAssistant, filepath: str) -> bool:
    """Check if a file exists on disk and is in authorized path."""
    if not hass.config.is_allowed_path(filepath):
        _LOGGER.warning("Path not allowed: %s", filepath)
        return False
    if not os.path.isfile(filepath):
        _LOGGER.warning("Not a file: %s", filepath)
        return False
    return True


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Dremel 3D Printer integration."""

    def get_api(service: ServiceCall) -> Dremel3DPrinter:
        """Return the host ip of a Dremel 3D Printer device."""
        device_id = service.data[ATTR_DEVICE_ID]
        dev_reg = device_registry.async_get(hass)
        if (device_entry := dev_reg.async_get(device_id)) is None:
            raise vol.Invalid("Invalid device ID")
        config_list = list(device_entry.config_entries)
        if len(config_list) == 0:
            raise vol.Invalid("No config entries for device ID")
        config_entry = list(device_entry.config_entries)[0]
        return hass.data[DOMAIN][config_entry].api

    async def print_job(service: ServiceCall) -> None:
        """Service to start a printing job."""
        api = get_api(service)
        filepath = service.data.get(ATTR_FILEPATH)
        url = service.data.get(ATTR_URL)
        try:
            if (
                filepath is not None
                and file_exists(hass, filepath)
                and filepath.lower().endswith(".gcode")
            ):
                result = await hass.async_add_executor_job(
                    api.start_print_from_file, filepath
                )
            elif url is not None and url.lower().endswith(".gcode"):
                result = await hass.async_add_executor_job(
                    api.start_print_from_url, url
                )
            hass.bus.async_fire(
                EVENT_DATA_NEW_PRINT_STATS,
                result,
            )
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.error(str(exc))

    async def pause_job(service: ServiceCall) -> None:
        """Service to pause a printing job."""
        api = get_api(service)
        await hass.async_add_executor_job(api.pause_print)

    async def resume_job(service: ServiceCall) -> None:
        """Service to resume a printing job."""
        api = get_api(service)
        await hass.async_add_executor_job(api.resume_print)

    async def stop_job(service: ServiceCall) -> None:
        """Service to stop a printing job."""
        api = get_api(service)
        await hass.async_add_executor_job(api.stop_print)

    hass.services.async_register(
        DOMAIN, SERVICE_PRINT_JOB, print_job, schema=SERVICE_PRINT_JOB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_PAUSE_JOB, pause_job, schema=SERVICE_COMMON_JOB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESUME_JOB, resume_job, schema=SERVICE_COMMON_JOB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_JOB, stop_job, schema=SERVICE_COMMON_JOB_SCHEMA
    )
