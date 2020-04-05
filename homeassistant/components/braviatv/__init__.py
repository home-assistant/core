"""The Bravia TV component."""
import asyncio
import logging

from bravia_tv import BraviaRC

from homeassistant.const import CONF_HOST, CONF_PIN
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CLIENTID_PREFIX, DOMAIN, NICKNAME

PLATFORMS = ["media_player"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Bravia TV component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    host = entry.data[CONF_HOST]
    pin = entry.data[CONF_PIN]

    braviarc = BraviaRC(host)

    await hass.async_add_executor_job(braviarc.connect, pin, CLIENTID_PREFIX, NICKNAME)

    if not braviarc.is_connected():
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = braviarc

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry):
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
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Update listener."""
    for component in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, component)
    hass.async_add_job(async_setup_entry(hass, config_entry))
