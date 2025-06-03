"""Support for Azure DevOps."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_PAT, CONF_PROJECT
from .coordinator import AzureDevOpsConfigEntry, AzureDevOpsDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AzureDevOpsConfigEntry) -> bool:
    """Set up Azure DevOps from a config entry."""

    # Create the data update coordinator
    coordinator = AzureDevOpsDataUpdateCoordinator(hass, entry, _LOGGER)

    # Store the coordinator in runtime data
    entry.runtime_data = coordinator

    # If a personal access token is set, authorize the client
    if entry.data.get(CONF_PAT) is not None:
        await coordinator.authorize(entry.data[CONF_PAT])

    # Set the project for the coordinator
    coordinator.project = await coordinator.get_project(entry.data[CONF_PROJECT])

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Azure DevOps config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
