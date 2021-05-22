"""The Nobø Ecohub integration."""
from __future__ import annotations

import logging

from pynobo import nobo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant, callback

from .const import CONF_SERIAL, DOMAIN, HUB, UNSUBSCRIBE

PLATFORMS = ["climate"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nobø Ecohub from a config entry."""

    # As there currently is no way to import options from yaml
    # when setting up a config entry, we fallback to adding
    # the options to the config entry and pull them out here if
    # they are missing from the options
    _async_import_options_from_data_if_missing(hass, entry)

    serial = entry.data.get(CONF_SERIAL)
    ip_address = entry.data.get(CONF_IP_ADDRESS)
    name = entry.title
    discover = ip_address is None
    hub = nobo(serial=serial, ip=ip_address, discover=discover, loop=hass.loop)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {HUB: hub}

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    unsubscribe = entry.add_update_listener(options_update_listener)
    hass.data[DOMAIN][entry.entry_id][UNSUBSCRIBE] = unsubscribe

    _LOGGER.info(
        "Nobø Ecohub '%s' is up and running on %s:%s", name, ip_address, serial
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    hub = hass.data[DOMAIN][entry.entry_id][HUB]
    serial = entry.data.get(CONF_SERIAL)
    ip_address = entry.data.get(CONF_IP_ADDRESS)
    name = entry.title
    await hub.stop()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][entry.entry_id][UNSUBSCRIBE]()
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.info("Nobø Ecohub '%s' on %s:%s is stopped", name, ip_address, serial)

    return unload_ok


async def options_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


@callback
def _async_import_options_from_data_if_missing(hass: HomeAssistant, entry: ConfigEntry):
    options = dict(entry.options)
    data = {}
    importable_options = [CONF_COMMAND_OFF, CONF_COMMAND_ON]
    found = False
    for key in entry.data:
        if key in importable_options and key not in options:
            options[key] = entry.data[key]
            found = True
        else:
            data[key] = entry.data[key]

    if found:
        hass.config_entries.async_update_entry(entry, data=data, options=options)
