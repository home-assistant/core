"""The Vivotek camera component."""

import logging
from typing import Any

from libpyvivotek.vivotek import VivotekCamera, VivotekCameraError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_DIGEST_AUTHENTICATION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_SECURITY_LEVEL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CAMERA]

type VivotekConfigEntry = ConfigEntry[VivotekCamera]


def build_cam_client(data: dict[str, Any]) -> VivotekCamera:
    """Build the Vivotek camera client from the provided configuration data."""
    return VivotekCamera(
        host=data[CONF_IP_ADDRESS],
        port=data[CONF_PORT],
        verify_ssl=data[CONF_VERIFY_SSL],
        usr=data[CONF_USERNAME],
        pwd=data[CONF_PASSWORD],
        digest_auth=(data[CONF_AUTHENTICATION] == HTTP_DIGEST_AUTHENTICATION),
        sec_lvl=data[CONF_SECURITY_LEVEL],
    )


async def async_build_and_test_cam_client(
    hass: HomeAssistant, data: dict[str, Any]
) -> VivotekCamera:
    """Build the client and test if the provided configuration is valid."""
    cam_client = build_cam_client(data)
    await hass.async_add_executor_job(cam_client.get_mac)

    return cam_client


async def async_setup_entry(hass: HomeAssistant, entry: VivotekConfigEntry) -> bool:
    """Set up the Vivotek component from a config entry."""

    try:
        cam_client = await async_build_and_test_cam_client(hass, dict(entry.data))
    except VivotekCameraError as err:
        raise ConfigEntryError("Failed to connect to camera") from err

    entry.runtime_data = cam_client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VivotekConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
