"""The Flipr integration."""

import logging

from flipr_api import FliprAPIRestClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

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
