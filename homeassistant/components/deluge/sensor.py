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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DelugeGetSessionStatusKeys, DelugeSensorType
from .coordinator import DelugeConfigEntry, DelugeDataUpdateCoordinator
from .entity import DelugeEntity


def get_state(data: dict[str, float], key: str) -> str | float:
    """Get current download/upload state."""
    upload = data[DelugeGetSessionStatusKeys.UPLOAD_RATE.value]
    download = data[DelugeGetSessionStatusKeys.DOWNLOAD_RATE.value]
    protocol_upload = data[DelugeGetSessionStatusKeys.DHT_UPLOAD_RATE.value]
    protocol_download = data[DelugeGetSessionStatusKeys.DHT_DOWNLOAD_RATE.value]

    # if key is CURRENT_STATUS, we just return whether we are uploading / downloading / idle
    if key == DelugeSensorType.CURRENT_STATUS_SENSOR:
        if upload > 0 and download > 0:
            return "seeding_and_downloading"
        if upload > 0 and download == 0:
            return "seeding"
        if upload == 0 and download > 0:
            return "downloading"
        return STATE_IDLE

    # if not, return the transfer rate for the given key
    rate = 0.0
    if key == DelugeSensorType.DOWNLOAD_SPEED_SENSOR:
        rate = download
    elif key == DelugeSensorType.UPLOAD_SPEED_SENSOR:
        rate = upload
    elif key == DelugeSensorType.PROTOCOL_TRAFFIC_DOWNLOAD_SPEED_SENSOR:
        rate = protocol_download
    else:
        rate = protocol_upload

    # convert to KiB/s and round
    kb_spd = rate / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


@dataclass(frozen=True)
class DelugeSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Deluge sensor."""

    value: Callable[[dict[str, float]], Any] = lambda val: val


SENSOR_TYPES: tuple[DelugeSensorEntityDescription, ...] = (
    DelugeSensorEntityDescription(
        key=DelugeSensorType.CURRENT_STATUS_SENSOR.value,
        translation_key="status",
        value=lambda data: get_state(
            data, DelugeSensorType.CURRENT_STATUS_SENSOR.value
        ),
        device_class=SensorDeviceClass.ENUM,
        options=["seeding_and_downloading", "seeding", "downloading", "idle"],
    ),
    DelugeSensorEntityDescription(
        key=DelugeSensorType.DOWNLOAD_SPEED_SENSOR.value,
        translation_key=DelugeSensorType.DOWNLOAD_SPEED_SENSOR.value,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: get_state(
            data, DelugeSensorType.DOWNLOAD_SPEED_SENSOR.value
        ),
    ),
    DelugeSensorEntityDescription(
        key=DelugeSensorType.UPLOAD_SPEED_SENSOR.value,
        translation_key=DelugeSensorType.UPLOAD_SPEED_SENSOR.value,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: get_state(data, DelugeSensorType.UPLOAD_SPEED_SENSOR.value),
    ),
    DelugeSensorEntityDescription(
        key=DelugeSensorType.PROTOCOL_TRAFFIC_UPLOAD_SPEED_SENSOR.value,
        translation_key=DelugeSensorType.PROTOCOL_TRAFFIC_UPLOAD_SPEED_SENSOR.value,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: get_state(
            data, DelugeSensorType.PROTOCOL_TRAFFIC_UPLOAD_SPEED_SENSOR.value
        ),
    ),
    DelugeSensorEntityDescription(
        key=DelugeSensorType.PROTOCOL_TRAFFIC_DOWNLOAD_SPEED_SENSOR.value,
        translation_key=DelugeSensorType.PROTOCOL_TRAFFIC_DOWNLOAD_SPEED_SENSOR.value,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: get_state(
            data, DelugeSensorType.PROTOCOL_TRAFFIC_DOWNLOAD_SPEED_SENSOR.value
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DelugeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
