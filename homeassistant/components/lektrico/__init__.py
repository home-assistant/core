"""The Lektrico Charging Station integration."""
from __future__ import annotations

import logging

from lektricowifi import lektricowifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DATA_LEKTRICO_CLIENT, DOMAIN

# from homeassistant.components.lektrico.sensor import LektricoSensor


# List the platforms that you want to support.
PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lektrico Charging Station from a config entry."""
    session = async_get_clientsession(hass)
    charger = lektricowifi.Charger(
        entry.data[CONF_HOST],
        session=session,
    )

    # Ensure we can connect to it
    try:
        await charger.charger_info()
    except lektricowifi.ChargerConnectionError as exception:
        logging.getLogger(__name__).debug("Unable to connect: %s", exception)
        raise ConfigEntryNotReady from exception

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_LEKTRICO_CLIENT: charger}
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # hass.data[DOMAIN].pop(entry.entry_id)
        # Cleanup
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok
