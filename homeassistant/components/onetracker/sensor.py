"""Configure the platform for OneTracker."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import OneTrackerDataUpdateCoordinator
from .parcel import ParcelEntity

_LOGGER = logging.getLogger(__name__)
import json


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry example."""
    # assuming API object stored here by __init__.py
    # config = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.warning("Entry %s", json.dumps(entry.as_dict()))
    config = entry.data
    _LOGGER.warning("Config %s", config)

    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #
    coordinator = OneTrackerDataUpdateCoordinator(hass, config=config)
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.warning("Post async_config_entry_first_refresh")
    _LOGGER.warning("Data %s", coordinator.data["parcels"])

    async_add_entities(
        ParcelEntity(coordinator, parcel) for parcel in enumerate(coordinator.data)
    )
