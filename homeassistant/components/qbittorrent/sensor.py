"""Support for monitoring the qBittorrent API."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any
from datetime import datetime, timezone


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    STATE_ATTR_TORRENT_INFO,
    STATE_DOWNLOADING,
    STATE_SEEDING,
    STATE_UP_DOWN,
)
from .coordinator import QBittorrentDataCoordinator

_LOGGER = logging.getLogger(__name__)



@dataclass(frozen=True, kw_only=True)
class QBittorrentSensorEntityDescription(SensorEntityDescription):
    """Entity description class for qBittorent sensors."""

    val_func: Callable[[QBittorrentDataCoordinator], StateType]
    extra_state_attr_func: Callable[[Any], dict[str, str]] | None = None


SENSOR_TYPES: tuple[QBittorrentSensorEntityDescription, ...] = (
    QBittorrentSensorEntityDescription(
        key="status", 
        translation_key="current_status", 
        name="Status",
        device_class=SensorDeviceClass.ENUM,
        options=[STATE_IDLE, STATE_UP_DOWN, STATE_SEEDING, STATE_DOWNLOADING],
        val_func=lambda coordinator: get_state(
            coordinator.data["server_state"]["up_info_speed"], coordinator.data["server_state"]["dl_info_speed"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key="download",
        translation_key="download_speed",
        name="Download Speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        val_func=lambda coordinator: float(coordinator.data["server_state"]["dl_info_speed"]),
    ),
    QBittorrentSensorEntityDescription(
        key="upload",
        translation_key="upload_speed",
        name="Upload Speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        val_func=lambda coordinator: float(coordinator.data["server_state"]["up_info_speed"]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up qBittorrent sensor entries."""

    coordinator: QBittorrentDataCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        QBittorrentSensor(coordinator, description) for description in SENSOR_TYPES
    )


class QBittorrentSensor(
    CoordinatorEntity[QBittorrentDataCoordinator], SensorEntity
):
    """Representation of a qBittorrent sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QBittorrentDataCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the qBittorrent sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="QBittorrent",
        )

    @property
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.val_func(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes, if any."""
        if attr_func := self.entity_description.extra_state_attr_func:
            return attr_func(self.coordinator)
        return None


def get_state(upload: int, download: int) -> str:
    """Get current download/upload state."""
    if upload > 0 and download > 0:
        return STATE_UP_DOWN
    if upload > 0 and download == 0:
        return STATE_SEEDING
    if upload == 0 and download > 0:
        return STATE_DOWNLOADING
    return STATE_IDLE
