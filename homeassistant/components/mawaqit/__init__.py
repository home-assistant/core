"""The mawaqit_prayer_times component."""

import logging

from dateutil import parser as date_parser

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store

from . import utils
from .const import (
    DOMAIN,
    MAWAQIT_PRAY_TIME,
    MAWAQIT_STORAGE_KEY,
    MAWAQIT_STORAGE_VERSION,
    MOSQUES_COORDINATOR,
    PRAYER_TIMES_COORDINATOR,
)
from .coordinator import MosqueCoordinator, PrayerTimeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


def is_date_parsing(date_str) -> bool:
    """Check if the given string can be parsed into a date."""
    try:
        date_parser.parse(date_str)
    except ValueError:
        return False
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Mawaqit Prayer Component."""

    # Initialize MosqueCoordinator
    mosque_coordinator = MosqueCoordinator(hass, config_entry)
    await mosque_coordinator.async_config_entry_first_refresh()

    # Initialize PrayerTimeCoordinator (API Data)
    prayer_time_coordinator = PrayerTimeCoordinator(hass, config_entry)
    await prayer_time_coordinator.async_config_entry_first_refresh()

    # Ensure prayer data exists before initializing sensors
    if not prayer_time_coordinator.data:
        _LOGGER.error("Prayer times data is empty, sensors will not be created")
        return False

    config_entry.runtime_data = {
        MOSQUES_COORDINATOR: mosque_coordinator,
        PRAYER_TIMES_COORDINATOR: prayer_time_coordinator,
    }

    try:
        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    except Exception as err:
        raise ConfigEntryNotReady from err

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Mawaqit Prayer entry from config_entry."""

    if DOMAIN in hass.data:
        if hass.data[DOMAIN].event_unsub:
            hass.data[DOMAIN].event_unsub()
        hass.data.pop(DOMAIN)

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Remove Mawaqit Prayer entry from config_entry."""
    _LOGGER.debug("Started clearing data")

    store: Store = Store(hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY)
    await utils.clear_storage_entry(store, MAWAQIT_PRAY_TIME)

    _LOGGER.debug("Finished clearing data")
