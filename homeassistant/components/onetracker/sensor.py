"""Configure the platform for OneTracker."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import OneTrackerDataUpdateCoordinator
from .parcel import ParcelEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry example."""

    config = entry.data

    coordinator = OneTrackerDataUpdateCoordinator(hass, config=config)
    await coordinator.async_config_entry_first_refresh()

    entities = list(
        map(lambda parcel: ParcelEntity(coordinator, parcel), coordinator.data)
    )

    async_add_entities(entities)
