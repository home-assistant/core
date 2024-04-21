"""The solax component."""

import asyncio
from importlib.metadata import entry_points
import logging

import solax
from solax import RealTimeAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SOLAX_INVERTER, DOMAIN, SOLAX_ENTRY_POINT_GROUP

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

INVERTERS_ENTRY_POINTS = {
    ep.name: ep.load() for ep in entry_points(group=SOLAX_ENTRY_POINT_GROUP)
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the sensors from a ConfigEntry."""

    invset = set()
    if (CONF_SOLAX_INVERTER in entry.data) and entry.data.get(
        CONF_SOLAX_INVERTER
    ) is not None:
        invset.add(INVERTERS_ENTRY_POINTS.get(entry.data[CONF_SOLAX_INVERTER]))
    else:
        for ep in INVERTERS_ENTRY_POINTS.values():
            invset.add(ep)

    _LOGGER.debug("solax inverter set %s", invset)

    try:
        inverter = await solax.discover(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_PORT],
            entry.data[CONF_PASSWORD],
            inverters=invset,
            return_when=asyncio.FIRST_COMPLETED,
        )
        api = RealTimeAPI(inverter)
        await api.get_data()
    except Exception as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
