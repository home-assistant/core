"""The Unifi Video integration."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
import requests
from uvcclient import nvr

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Unifi Video component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Unifi Video from a config entry."""
    nvrconn = await hass.async_add_executor_job(_get_nvrconn, entry)
    hass.data[DOMAIN]["nvrconn"] = nvrconn
    hass.data[DOMAIN]["camera_password"] = entry.data[CONF_PASSWORD]
    hass.data[DOMAIN]["camera_id_field"] = (
        "_id" if nvrconn.server_version >= (3, 2, 0) else "uuid"
    )

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                return await hass.async_add_executor_job(
                    _get_cameras,
                    hass.data[DOMAIN]["nvrconn"],
                    hass.data[DOMAIN]["camera_id_field"],
                )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="uvc-camera",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=10),
    )

    hass.data[DOMAIN]["coordinator"] = coordinator

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


def _get_nvrconn(entry: ConfigEntry) -> nvr:
    return nvr.UVCRemote(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_API_KEY],
        ssl=entry.data[CONF_SSL],
    )


def _get_cameras(nvrconn: nvr, id_field: str):
    try:
        cameras = nvrconn._uvc_request("/api/2.0/camera")["data"]
    except nvr.NotAuthorized:
        _LOGGER.error("Authorization failure while connecting to NVR")
        return False
    except nvr.NvrError as ex:
        _LOGGER.error("NVR refuses to talk to me: %s", str(ex))
        raise PlatformNotReady from ex
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to NVR: %s", str(ex))
        raise PlatformNotReady from ex
    return {
        camera[id_field]: camera
        for camera in cameras
        if "airCam" not in camera["model"]
    }


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
