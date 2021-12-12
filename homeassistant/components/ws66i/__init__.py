"""The Soundavo WS66i 6-Zone Amplifier integration."""
import logging

from pyws66i import get_ws66i

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .config_flow import validate_input
from .const import CONF_NOT_FIRST_RUN, DOMAIN, FIRST_RUN, WS66I_OBJECT

PLATFORMS = ["media_player"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Soundavo WS66i 6-Zone Amplifier from a config entry."""

    # double negative to handle absence of value
    first_run = not bool(entry.data.get(CONF_NOT_FIRST_RUN))
    if first_run:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_NOT_FIRST_RUN: True}
        )
    else:
        # Need to verify we can connect
        try:
            _ = await validate_input(hass, entry.data)
        except ConnectionError as err:
            raise ConfigEntryNotReady from err

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    addr = entry.data[CONF_IP_ADDRESS]
    ws66i = get_ws66i(addr)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        WS66I_OBJECT: ws66i,
        FIRST_RUN: first_run,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][entry.entry_id][WS66I_OBJECT].close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
