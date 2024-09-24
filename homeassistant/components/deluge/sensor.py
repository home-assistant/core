"""Support for monitoring the Deluge BitTorrent client API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import STATE_IDLE, Platform, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import DelugeConfigEntry
from .const import CURRENT_STATUS, DATA_KEYS, DOWNLOAD_SPEED, UPLOAD_SPEED
from .coordinator import DelugeDataUpdateCoordinator
from .entity import DelugeEntity


def get_state(data: dict[str, float], key: str) -> str | float:
    """Get current download/upload state."""
    upload = data[DATA_KEYS[0]] - data[DATA_KEYS[2]]
    download = data[DATA_KEYS[1]] - data[DATA_KEYS[3]]
    if key == CURRENT_STATUS:
        if upload > 0 and download > 0:
            return "seeding_and_downloading"
        if upload > 0 and download == 0:
            return "seeding"
        if upload == 0 and download > 0:
            return "downloading"
        return STATE_IDLE
    kb_spd = float(upload if key == UPLOAD_SPEED else download) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


@dataclass(frozen=True)
class DelugeSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Deluge sensor."""

    value: Callable[[dict[str, float]], Any] = lambda val: val


SENSOR_TYPES: tuple[DelugeSensorEntityDescription, ...] = (
    DelugeSensorEntityDescription(
        key=CURRENT_STATUS,
        translation_key="status",
        value=lambda data: get_state(data, CURRENT_STATUS),
        device_class=SensorDeviceClass.ENUM,
        options=["seeding_and_downloading", "seeding", "downloading", "idle"],
    ),
    DelugeSensorEntityDescription(
        key=DOWNLOAD_SPEED,
        translation_key="download_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: get_state(data, DOWNLOAD_SPEED),
    ),
    DelugeSensorEntityDescription(
        key=UPLOAD_SPEED,
        translation_key="upload_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: get_state(data, UPLOAD_SPEED),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DelugeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Deluge sensor."""
    async_add_entities(
        DelugeSensor(entry.runtime_data, description) for description in SENSOR_TYPES
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
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value(self.coordinator.data[Platform.SENSOR])
