"""The fritzbox_callmonitor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .base import FritzBoxPhonebook
from .const import CONF_PHONEBOOK, CONF_PREFIXES, PLATFORMS

_LOGGER = logging.getLogger(__name__)

FritzBoxCallMonitorConfigEntry = ConfigEntry["FritzBoxCallMonitorData"]


@dataclass
class FritzBoxCallMonitorData:
    """Store FritzBox Call Monitor data."""

    phonebook: FritzBoxPhonebook
    update_listener: Callable[[], None]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: FritzBoxCallMonitorConfigEntry
) -> bool:
    """Set up the fritzbox_callmonitor platforms."""
    fritzbox_phonebook = FritzBoxPhonebook(
        host=config_entry.data[CONF_HOST],
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        phonebook_id=config_entry.data[CONF_PHONEBOOK],
        prefixes=config_entry.options.get(CONF_PREFIXES),
    )

    try:
        await hass.async_add_executor_job(fritzbox_phonebook.init_phonebook)
    except FritzSecurityError as ex:
        _LOGGER.error(
            (
                "User has insufficient permissions to access AVM FRITZ!Box settings and"
                " its phonebooks: %s"
            ),
            ex,
        )
        return False
    except FritzConnectionException as ex:
        _LOGGER.error("Invalid authentication: %s", ex)
        return False
    except RequestsConnectionError as ex:
        _LOGGER.error("Unable to connect to AVM FRITZ!Box call monitor: %s", ex)
        raise ConfigEntryNotReady from ex

    config_entry.runtime_data = FritzBoxCallMonitorData(
        phonebook=fritzbox_phonebook,
        update_listener=config_entry.add_update_listener(update_listener),
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: FritzBoxCallMonitorConfigEntry
) -> bool:
    """Unloading the fritzbox_callmonitor platforms."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    config_entry.runtime_data.update_listener()
    return unload_ok


async def update_listener(
    hass: HomeAssistant, config_entry: FritzBoxCallMonitorConfigEntry
) -> None:
    """Update listener to reload after option has changed."""
    await hass.config_entries.async_reload(config_entry.entry_id)
