"""The Coolmaster integration."""

from pycoolmasternet_async import CoolMasterNet

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DATA_API, DATA_INFO, DOMAIN


async def async_setup(hass, config):
    """Set up Coolmaster components."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Coolmaster from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    cool = CoolMasterNet(host, port)
    try:
        info = await cool.info()
        if not info:
            raise ConfigEntryNotReady()
    except (OSError, ConnectionRefusedError, TimeoutError) as error:
        raise ConfigEntryNotReady() from error

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_API: cool,
        DATA_INFO: info,
    }
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload a Coolmaster config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "climate")

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
