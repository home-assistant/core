"""The fritzbox_netmonitor integration."""
import asyncio
from functools import partial

from fritzconnection.core.exceptions import FritzConnectionException
from fritzconnection.lib.fritzstatus import FritzStatus
from requests.exceptions import ConnectionError

from homeassistant.const import CONF_HOST

from .const import DOMAIN, LOGGER, PLATFORMS


async def async_setup(hass, config):
    """Set up the fritzbox_netmonitor integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up the fritzbox_netmonitor platforms."""
    host = entry.data[CONF_HOST]

    try:
        fritz_status = await hass.async_add_executor_job(
            partial(FritzStatus, address=host)
        )
    except (
        ValueError,
        TypeError,
        ConnectionError,
        FritzConnectionException,
    ) as error:
        LOGGER.error(
            "Failed to establish connection to FRITZ!Box (%s): %s", host, error
        )
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = [fritz_status, host]

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unloading the fritzbox_netmonitor platforms."""

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
