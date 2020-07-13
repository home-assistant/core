"""The Risco integration."""
import asyncio

from pyrisco import CannotConnectError, RiscoAPI, UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME
from homeassistant.core import EVENT_HOMEASSISTANT_STOP, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DATA_REMOVE_LISTENER, DATA_RISCO, DOMAIN

PLATFORMS = ["alarm_control_panel"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Risco component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Risco from a config entry."""
    data = entry.data
    risco = RiscoAPI(data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PIN])
    try:
        await risco.login()
    except (CannotConnectError, UnauthorizedError) as error:
        raise ConfigEntryNotReady() from error

    async def _close(event):
        await risco.close()

    remove_listener = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_RISCO: risco,
        DATA_REMOVE_LISTENER: remove_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


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
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data[DATA_RISCO].close()
        data[DATA_REMOVE_LISTENER]()

    return unload_ok
