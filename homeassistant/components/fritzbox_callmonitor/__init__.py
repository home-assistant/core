"""The fritzbox_callmonitor integration."""
import asyncio

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .base import FritzBoxPhonebook
from .const import CONF_PHONEBOOK, CONF_PREFIXES, DOMAIN, PLATFORMS


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
        prefixes=entry.data[CONF_PREFIXES],
    )
    await hass.async_add_executor_job(phonebook.init_phonebook)
    await hass.async_add_executor_job(phonebook.update_phonebook)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = phonebook

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
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
