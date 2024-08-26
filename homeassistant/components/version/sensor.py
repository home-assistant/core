"""Sensor that can display the current Home Assistant versions."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import VersionConfigEntry
from .const import CONF_SOURCE, DEFAULT_NAME
from .entity import VersionEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VersionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up version sensors."""
    coordinator = entry.runtime_data
    if (entity_name := entry.data[CONF_NAME]) == DEFAULT_NAME:
        entity_name = entry.title

    version_sensor_entities: list[VersionSensorEntity] = [
        VersionSensorEntity(
            coordinator=coordinator,
            entity_description=SensorEntityDescription(
                key=str(entry.data[CONF_SOURCE]),
                name=entity_name,
                translation_key="version",
            ),
        )
    ]

    async_add_entities(version_sensor_entities)


class VersionSensorEntity(VersionEntity, SensorEntity):
    """Version sensor entity class."""

    @property
    def native_value(self) -> StateType:
        """Return the native value of this sensor."""
        return self.coordinator.version

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes of this sensor."""
        return self.coordinator.version_data
