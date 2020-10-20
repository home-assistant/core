"""The fritzbox_callmonitor integration."""
from asyncio import gather
import logging

from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady

from .base import FritzBoxPhonebook
from .const import (
    CONF_PHONEBOOK,
    CONF_PREFIXES,
    DOMAIN,
    FRITZ_BOX_PHONEBOOK_OBJECT,
    PLATFORMS,
    UNDO_UPDATE_LISTENER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the fritzbox_callmonitor integration."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the fritzbox_callmonitor platforms."""
    phonebook = FritzBoxPhonebook(
        host=config_entry.data[CONF_HOST],
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        phonebook_id=config_entry.data[CONF_PHONEBOOK],
        prefixes=config_entry.options.get(CONF_PREFIXES),
    )

    try:
        await hass.async_add_executor_job(phonebook.init_phonebook)
    except (
        RequestsConnectionError,
        FritzSecurityError,
        FritzConnectionException,
    ) as ex:
        _LOGGER.error("Unable to connect to AVM FRITZ!Box call monitor: %s", ex)
        raise ConfigEntryNotReady from ex

    undo_listener = config_entry.add_update_listener(update_listener)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        FRITZ_BOX_PHONEBOOK_OBJECT: phonebook,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unloading the fritzbox_callmonitor platforms."""

    unload_ok = all(
        await gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Update listener to reload after option has changed."""
    await hass.config_entries.async_reload(config_entry.entry_id)
