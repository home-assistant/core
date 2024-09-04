"""The Flipr integration."""

import logging

from flipr_api import FliprAPIRestClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ENTRY_FLIPR_COORDINATORS, CONF_ENTRY_HUB_COORDINATORS, DOMAIN
from .coordinator import FliprDataUpdateCoordinator, HubDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up flipr from a config entry."""
    hass.data.setdefault(DOMAIN, {})

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

    hub_coordinators = []
    for hub_id in ids["hub"]:
        hub_coordinator = HubDataUpdateCoordinator(hass, entry, hub_id)
        await hub_coordinator.async_config_entry_first_refresh()
        hub_coordinators.append(hub_coordinator)
    hass.data[DOMAIN][CONF_ENTRY_HUB_COORDINATORS] = hub_coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(CONF_ENTRY_FLIPR_COORDINATORS)
        hass.data[DOMAIN].pop(CONF_ENTRY_HUB_COORDINATORS)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry."""
    _LOGGER.info("Migration of flipr config from version %s", entry.version)

    if entry.version == 1:
        # In version 1, we have flipr id as config entry unique id and one device per config entry.
        # We need to migrate to a new config entry that may contain multiple devices. So we change the title and entry data to match config_flow evolution.
        login = entry.data[CONF_EMAIL]
        new_title = f"Flipr {login}"

        new_data = {**entry.data}
        # We do not store anymore the flipr_id in the config entry.
        new_data.pop("flipr_id")

        hass.config_entries.async_update_entry(
            entry, data=new_data, title=new_title, version=2
        )

        _LOGGER.info("Migration of flipr config to version 2 successful")

    return True
