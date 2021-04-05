"""The Unifi Video integration."""
import asyncio
import logging

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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]


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
        "id" if nvrconn.server_version >= (3, 2, 0) else "uuid"
    )

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
