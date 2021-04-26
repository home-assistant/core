"""The Dune HD component."""
import asyncio

from pdunehd import DuneHDPlayer

from homeassistant.const import CONF_HOST

from .const import DOMAIN

PLATFORMS = ["media_player"]


async def async_setup_entry(hass, config_entry):
    """Set up a config entry."""
    host = config_entry.data[CONF_HOST]

    player = DuneHDPlayer(host)

    hass.data[DOMAIN][config_entry.entry_id] = player

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
