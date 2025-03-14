"""The Flipr integration."""

from collections import Counter
import logging

from flipr_api import FliprAPIRestClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .coordinator import (
    FliprConfigEntry,
    FliprData,
    FliprDataUpdateCoordinator,
    FliprHubDataUpdateCoordinator,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: FliprConfigEntry) -> bool:
    """Set up flipr from a config entry."""

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
        flipr_coordinator = FliprDataUpdateCoordinator(hass, entry, client, flipr_id)
        await flipr_coordinator.async_config_entry_first_refresh()
        flipr_coordinators.append(flipr_coordinator)

    hub_coordinators = []
    for hub_id in ids["hub"]:
        hub_coordinator = FliprHubDataUpdateCoordinator(hass, entry, client, hub_id)
        await hub_coordinator.async_config_entry_first_refresh()
        hub_coordinators.append(hub_coordinator)

    entry.runtime_data = FliprData(flipr_coordinators, hub_coordinators)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def detect_invalid_old_configuration(hass: HomeAssistant, entry: ConfigEntry):
    """Detect invalid old configuration and raise error if found."""

    def find_duplicate_entries(entries):
        values = [e.data["email"] for e in entries]
        _LOGGER.debug("Detecting duplicates in values : %s", values)
        return any(count > 1 for count in Counter(values).values())

    entries = hass.config_entries.async_entries(DOMAIN)

    if find_duplicate_entries(entries):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "duplicate_config",
            breaks_in_ha_version="2025.4.0",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="duplicate_config",
        )

        raise ConfigEntryError(
            "Duplicate entries found for flipr with the same user email. Please remove one of it manually. Multiple fliprs will be automatically detected after restart."
        )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry."""
    _LOGGER.debug("Migration of flipr config from version %s", entry.version)

    if entry.version == 1:
        # In version 1, we have flipr device as config entry unique id
        # and one device per config entry.
        # We need to migrate to a new config entry that may contain multiple devices.
        # So we change the entry data to match config_flow evolution.
        login = entry.data[CONF_EMAIL]

        hass.config_entries.async_update_entry(entry, version=2, unique_id=login)

        _LOGGER.debug("Migration of flipr config to version 2 successful")

    return True
