"""The Flipr integration."""

from collections import Counter
import logging

from flipr_api import FliprAPIRestClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_ENTRY_FLIPR_COORDINATORS, DOMAIN
from .coordinator import FliprDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up flipr from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Detect invalid old config entry and raise error if found
    detect_invalid_old_configuration(hass, entry)

    config = entry.data

    username = config[CONF_EMAIL]
    password = config[CONF_PASSWORD]

    _LOGGER.debug("Initializing Flipr client %s", username)
    client = FliprAPIRestClient(username, password)
    ids = await hass.async_add_executor_job(client.search_all_ids)

    _LOGGER.debug("List of devices ids : %s", ids)

    flipr_coordinators = []
    for flipr_id in ids["flipr"]:
        flipr_coordinator = FliprDataUpdateCoordinator(hass, entry, flipr_id)
        await flipr_coordinator.async_config_entry_first_refresh()
        flipr_coordinators.append(flipr_coordinator)
    hass.data[DOMAIN][CONF_ENTRY_FLIPR_COORDINATORS] = flipr_coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(CONF_ENTRY_FLIPR_COORDINATORS)

    return unload_ok


def detect_invalid_old_configuration(hass: HomeAssistant, entry: ConfigEntry):
    """Detect invalid old configuration and raise error if found."""

    def find_duplicate_entries(entries):
        values = [e.data["email"] for e in entries]
        _LOGGER.debug("Detecting duplicates in values : %s", values)
        return any(count > 1 for count in Counter(values).values())

    entries = hass.config_entries.async_entries(DOMAIN)

    if find_duplicate_entries(entries):
        raise ConfigEntryError(
            "Duplicate entries found for flipr with the same user email. Please remove one of it manually. Multiple fliprs will be automatically detected after restart."
        )
