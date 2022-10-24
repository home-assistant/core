"""Support for Epic Games Store sensors."""
from __future__ import annotations

from epicstore_api import EpicGamesStoreAPI
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .coordinator import EGSUpdateCoordinator

# from .coordinator import EGSDataUpdateCoordinator

PARALLEL_UPDATES = 1

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = [
    SensorEntityDescription(
        key="free_game_1",
        name="Free game 1",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="free_game_2",
        name="Free game 2",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="next_free_game_1",
        name="Next free game 1",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="next_free_game_2",
        name="Next free game 2",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Epic Games Store sensors based on a config entry."""
    coordinator: EGSUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [EGSSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS],
        True
    )


class EGSSensor(SensorEntity):
    """Representation of a Epic Games Store sensor."""

    def __init__(
        self, coordinator: EGSUpdateCoordinator, entity_description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entity_description = entity_description
        self._attr_unique_id = self.entity_description.key

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data[self.entity_description.key]['end_at']
        return None

    @property
    def extra_state_attributes(self):
        """Return additional sensor state attributes."""
        if self.coordinator.data:
            return {
                "title": self.coordinator.data[self.entity_description.key]["title"],
                "url": self.coordinator.data[self.entity_description.key]["url"],
                "thumbnail": self.coordinator.data[self.entity_description.key]["thumbnail"],
                "start_at": self.coordinator.data[self.entity_description.key]["start_at"],
                "end_at": self.coordinator.data[self.entity_description.key]["end_at"],
            }
        return {}
