"""The solax component."""

import logging

import solax
from solax import RealTimeAPI
from solax.discovery import REGISTRY

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SOLAX_INVERTER, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the sensors from a ConfigEntry."""

    registry_hash = {cls.__name__: cls for cls in REGISTRY}

    invset = set()
    for cls_name in entry.data[CONF_SOLAX_INVERTER]:
        invset.add(registry_hash[cls_name])

    _LOGGER.debug("solax inverter set %s", invset)

    try:
        inverter = await solax.discover(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_PORT],
            entry.data[CONF_PASSWORD],
            inverters=invset,
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
