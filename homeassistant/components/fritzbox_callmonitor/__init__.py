"""The fritzbox_callmonitor integration."""
import asyncio

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .base import FritzBoxPhonebook
from .const import (
    CONF_PHONEBOOK,
    CONF_PREFIXES,
    DOMAIN,
    FRITZ_BOX_PHONEBOOK_OBJECT,
    PLATFORMS,
    UNDO_UPDATE_LISTENER,
)


async def async_setup(hass, config):
    """Set up the fritzbox_callmonitor integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up the fritzbox_callmonitor platforms."""
    phonebook = FritzBoxPhonebook(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        phonebook_id=entry.data[CONF_PHONEBOOK],
        prefixes=entry.options.get(CONF_PREFIXES),
    )
    await hass.async_add_executor_job(phonebook.init_phonebook)
    await hass.async_add_executor_job(phonebook.update_phonebook)

    undo_listener = entry.add_update_listener(update_listener)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        FRITZ_BOX_PHONEBOOK_OBJECT: phonebook,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unloading the fritzbox_callmonitor platforms."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Update listener to reload after option has changed."""
    await hass.config_entries.async_reload(config_entry.entry_id)
