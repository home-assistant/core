"""The Vivotek camera component."""

from dataclasses import dataclass
import logging
from types import MappingProxyType
from typing import Any, TypedDict

from libpyvivotek import VivotekCamera

from homeassistant import config_entries
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

from .const import CONF_SECURITY_LEVEL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CAMERA]

type VivotekConfigEntry = config_entries.ConfigEntry[VivotekData]


class VivotekCameraConf(TypedDict):
    """Vivotek Camera configuration type."""

    authentication: str
    ip_address: str
    password: str
    port: int
    security_level: str
    ssl: bool
    username: str
    verify_ssl: bool


async def async_build_and_test_cam_client(
    hass: HomeAssistant,
    data: dict[str, Any] | MappingProxyType[str, Any] | VivotekCameraConf,
) -> VivotekCamera:
    """Build the client and test if the provided configuration is valid."""
    cam_client = VivotekCamera(
        host=data[CONF_IP_ADDRESS],
        port=data[CONF_PORT],
        verify_ssl=data[CONF_VERIFY_SSL],
        usr=data[CONF_USERNAME],
        pwd=data[CONF_PASSWORD],
        digest_auth=(data[CONF_AUTHENTICATION] == HTTP_DIGEST_AUTHENTICATION),
        sec_lvl=data[CONF_SECURITY_LEVEL],  # type: ignore[literal-required]
    )
    mac = await hass.async_add_executor_job(cam_client.get_mac)
    assert len(mac) > 0
    return cam_client


async def async_setup_entry(hass: HomeAssistant, entry: VivotekConfigEntry) -> bool:
    """Set up the Vivotek component from a config entry."""

    try:
        cam_client = await async_build_and_test_cam_client(hass, entry.data)
        entry.runtime_data = VivotekData(
            cam_client=cam_client,
        )
    except Exception:
        _LOGGER.exception("Unexpected exception during setup")
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@dataclass
class VivotekData:
    """Data for the Vivotek component."""

    cam_client: VivotekCamera
