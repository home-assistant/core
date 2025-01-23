"""The mawaqit_prayer_times component."""

import logging

from dateutil import parser as date_parser

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from . import utils
from .const import (
    DOMAIN,
    MAWAQIT_ALL_MOSQUES_NN,
    MAWAQIT_MY_MOSQUE_NN,
    MAWAQIT_PRAY_TIME,
    MAWAQIT_STORAGE_KEY,
    MAWAQIT_STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def is_date_parsing(date_str) -> bool:
    """Check if the given string can be parsed into a date."""
    try:
        date_parser.parse(date_str)
    except ValueError:
        return False
    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import the Mawaqit Prayer component from config."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Mawaqit Prayer Component."""

    hass.data.setdefault(DOMAIN, {})
    try:
        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    except Exception as err:
        raise ConfigEntryNotReady from err

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Mawaqit Prayer entry from config_entry."""

    if hass.data[DOMAIN].event_unsub:
        hass.data[DOMAIN].event_unsub()
    hass.data.pop(DOMAIN)

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Remove Mawaqit Prayer entry from config_entry."""
    _LOGGER.debug("Started clearing data")

    store: Store = Store(hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY)
    await utils.clear_storage_entry(store, MAWAQIT_MY_MOSQUE_NN)
    await utils.clear_storage_entry(store, MAWAQIT_ALL_MOSQUES_NN)
    await utils.clear_storage_entry(store, MAWAQIT_PRAY_TIME)
    # after adding MAWAQIT_MOSQ_LIST_DATA to storage we need to clear it here

    _LOGGER.debug("Finished clearing data")
