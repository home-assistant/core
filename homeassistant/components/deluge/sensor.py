"""Support for monitoring the Deluge BitTorrent client API."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_RATE_KILOBYTES_PER_SECOND, STATE_IDLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.typing import StateType

from . import DelugeEntity
from .const import CURRENT_STATUS, DATA_KEYS, DOMAIN, DOWNLOAD_SPEED, UPLOAD_SPEED
from .coordinator import DelugeDataUpdateCoordinator


def get_state(data: dict[str, float], key: str) -> str | float:
    """Get current download/upload state."""
    upload = data[DATA_KEYS[0]] - data[DATA_KEYS[2]]
    download = data[DATA_KEYS[1]] - data[DATA_KEYS[3]]
    if key == CURRENT_STATUS:
        if upload > 0 and download > 0:
            return "Up/Down"
        if upload > 0 and download == 0:
            return "Seeding"
        if upload == 0 and download > 0:
            return "Downloading"
        return STATE_IDLE
    kb_spd = float(upload if key == UPLOAD_SPEED else download) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


@dataclass
class DelugeSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Deluge sensor."""

    value: Callable[[dict[str, float]], Any] = lambda val: val


SENSOR_TYPES: tuple[DelugeSensorEntityDescription, ...] = (
    DelugeSensorEntityDescription(
        key=CURRENT_STATUS,
        name="Status",
        value=lambda data: get_state(data, CURRENT_STATUS),
    ),
    DelugeSensorEntityDescription(
        key=DOWNLOAD_SPEED,
        name="Down Speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: get_state(data, DOWNLOAD_SPEED),
    ),
    DelugeSensorEntityDescription(
        key=UPLOAD_SPEED,
        name="Up Speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: get_state(data, UPLOAD_SPEED),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up the Deluge sensor."""
    async_add_entities(
        DelugeSensor(hass.data[DOMAIN][entry.entry_id], description)
        for description in SENSOR_TYPES
    )


class DelugeSensor(DelugeEntity, SensorEntity):
    """Representation of a Deluge sensor."""

    entity_description: DelugeSensorEntityDescription

    def __init__(
        self,
        coordinator: DelugeDataUpdateCoordinator,
        description: DelugeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.config_entry.title} {description.name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value(self.coordinator.data[Platform.SENSOR])
