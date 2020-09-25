"""The fritzbox_netmonitor component."""
import asyncio
import logging

from fritzconnection.core.exceptions import FritzConnectionException
from fritzconnection.lib.fritzstatus import FritzStatus
from requests.exceptions import RequestException

from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Set up the AVM Fritz!Box platforms."""
    try:
        fritzbox_status = FritzStatus(address=entry.data[CONF_HOST])
    except (ValueError, TypeError, FritzConnectionException):
        fritzbox_status = None

    if fritzbox_status is None:
        _LOGGER.error(
            "Failed to establish connection to FRITZ!Box: %s", entry.data[CONF_HOST]
        )
        return False

    hass.data[DOMAIN][entry.entry_id] = fritzbox_status

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unloading the AVM Fritz!Box platforms."""
    fritz = hass.data[DOMAIN][entry.entry_id]
    await hass.async_add_executor_job(fritz.logout)

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
