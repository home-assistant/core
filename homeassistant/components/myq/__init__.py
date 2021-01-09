"""The MyQ integration."""
import asyncio
from datetime import timedelta
import logging

import pymyq
from pymyq.errors import InvalidCredentialsError, MyQError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_USERAGENT,
    DOMAIN,
    MYQ_COORDINATOR,
    MYQ_GATEWAY,
    PLATFORMS,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the MyQ component."""

    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up MyQ from a config entry."""

    if CONF_USERAGENT in entry.data:
        # If user agent exists in the config entry's data, pop it and move it to
        # options:
        data = {**entry.data}
        entry_updates = {}
        entry_updates["data"] = data
        entry_updates["options"] = {
            **entry.options,
            CONF_USERAGENT: data.pop(CONF_USERAGENT),
        }
        hass.config_entries.async_update_entry(entry, **entry_updates)

    websession = aiohttp_client.async_get_clientsession(hass)
    conf = entry.data

    try:
        myq = await pymyq.login(
            conf[CONF_USERNAME],
            conf[CONF_PASSWORD],
            websession,
            entry.options.get(CONF_USERAGENT, "pymyq"),
        )
    except InvalidCredentialsError as err:
        _LOGGER.error("There was an error while logging in: %s", err)
        return False
    except MyQError as err:
        raise ConfigEntryNotReady from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="myq devices",
        update_method=myq.update_device_info,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    unsub_options_update_listener = entry.add_update_listener(async_reload_entry)
    hass.data[DOMAIN][entry.entry_id] = {
        MYQ_GATEWAY: myq,
        MYQ_COORDINATOR: coordinator,
        "unsub_options_update_listener": unsub_options_update_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        cancel_listener = hass.data[DOMAIN][entry.entry_id][
            "unsub_options_update_listener"
        ]
        cancel_listener()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
