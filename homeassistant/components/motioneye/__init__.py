"""The motionEye integration."""
import asyncio
import logging
from typing import Any, Dict, Optional

from motioneye_client.client import (
    MotionEyeClient,
    MotionEyeClientError,
    MotionEyeClientInvalidAuth,
)
from motioneye_client.const import KEY_CAMERAS, KEY_ID

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CLIENT,
    CONF_COORDINATOR,
    CONF_ON_UNLOAD,
    CONF_PASSWORD_ADMIN,
    CONF_PASSWORD_SURVEILLANCE,
    CONF_USERNAME_ADMIN,
    CONF_USERNAME_SURVEILLANCE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]


def create_motioneye_client(
    *args: Any,
    **kwargs: Any,
) -> MotionEyeClient:
    """Create a MotionEyeClient."""
    return MotionEyeClient(*args, **kwargs)


def get_motioneye_unique_id(host: str, port: int, camera_id: int, name: str) -> str:
    """Get the unique_id for a motionEye entity."""
    return f"{host}:{port}_{camera_id}_{name}"


def get_camera_from_cameras(
    camera_id: int, data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Get an individual camera dict from a multiple cameras data response."""
    for camera in data.get(KEY_CAMERAS) or []:
        if camera.get(KEY_ID) == camera_id:
            return camera
    return None


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]):
    """Set up the motionEye component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up motionEye from a config entry."""
    client = create_motioneye_client(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        username_admin=entry.data.get(CONF_USERNAME_ADMIN),
        username_surveillance=entry.data.get(CONF_USERNAME_SURVEILLANCE),
        password_admin=entry.data.get(CONF_PASSWORD_ADMIN),
        password_surveillance=entry.data.get(CONF_PASSWORD_SURVEILLANCE),
    )

    try:
        await client.async_client_login()
    except MotionEyeClientInvalidAuth:
        # TODO: Add reauth handler.
        return False
    except MotionEyeClientError:
        raise ConfigEntryNotReady

    async def async_update_data():
        try:
            return await client.async_get_cameras()
        except MotionEyeClientError as exc:
            raise UpdateFailed(f"Error communicating with API: {exc}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_CLIENT: client,
        CONF_COORDINATOR: coordinator,
        CONF_ON_UNLOAD: [],
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        config_data = hass.data[DOMAIN].pop(entry.entry_id)
        await config_data[CONF_CLIENT].async_client_close()
        for func in config_data[CONF_ON_UNLOAD]:
            func()

    return unload_ok
