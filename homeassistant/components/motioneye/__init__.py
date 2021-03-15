"""The motionEye integration."""
import asyncio
from typing import Any, Dict

from motioneye_client.client import MotionEyeClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_BASE_URL, CONF_CLIENT, DOMAIN

PLATFORMS = ["camera"]


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]):
    """Set up the motionEye component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up motionEye from a config entry."""

    base_url = entry.data[CONF_BASE_URL]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    client = MotionEyeClient(base_url, username=username, password=password)

    if not await client.async_client_login():
        # TODO: Add reauth handler.
        await client.async_client_close()
        return False

    hass.data[DOMAIN][entry.entry_id] = {CONF_CLIENT: client}

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
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
