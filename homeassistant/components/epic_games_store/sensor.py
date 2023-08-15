"""Support for Epic Games Store sensors."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EGSUpdateCoordinator

PARALLEL_UPDATES = 1

SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        device_class=SensorDeviceClass.DATE,
        key="free_games",
        translation_key="free_games",
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.DATE,
        key="next_free_games",
        translation_key="next_free_games",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Epic Games Store sensors based on a config entry."""
    coordinator: EGSUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [EGSSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS],
    )


class EGSSensor(SensorEntity):
    """Representation of a Epic Games Store sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EGSUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{self.entity_description.key}-{self.coordinator.locale}"
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data[self.entity_description.key]["end_at"]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional sensor state attributes."""
        if self.coordinator.data:
            return self.coordinator.data[self.entity_description.key]
        return None
