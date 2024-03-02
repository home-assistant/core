"""Support for monitoring the qBittorrent API."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATE_DOWNLOADING, STATE_SEEDING, STATE_UP_DOWN
from .coordinator import QBittorrentDataCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_CURRENT_STATUS = "current_status"
SENSOR_TYPE_DOWNLOAD_SPEED = "download_speed"
SENSOR_TYPE_UPLOAD_SPEED = "upload_speed"
SENSOR_TYPE_ALL_TORRENTS = "all_torrents"
SENSOR_TYPE_PAUSED_TORRENTS = "paused_torrents"
SENSOR_TYPE_ACTIVE_TORRENTS = "active_torrents"
SENSOR_TYPE_INACTIVE_TORRENTS = "inactive_torrents"


def get_state(coordinator: QBittorrentDataCoordinator) -> str:
    """Get current download/upload state."""
    upload = coordinator.data["server_state"]["up_info_speed"]
    download = coordinator.data["server_state"]["dl_info_speed"]

    if upload > 0 and download > 0:
        return STATE_UP_DOWN
    if upload > 0 and download == 0:
        return STATE_SEEDING
    if upload == 0 and download > 0:
        return STATE_DOWNLOADING
    return STATE_IDLE


@dataclass(frozen=True, kw_only=True)
class QBittorrentSensorEntityDescription(SensorEntityDescription):
    """Entity description class for qBittorent sensors."""

    value_fn: Callable[[QBittorrentDataCoordinator], StateType]


SENSOR_TYPES: tuple[QBittorrentSensorEntityDescription, ...] = (
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_CURRENT_STATUS,
        translation_key="current_status",
        device_class=SensorDeviceClass.ENUM,
        options=[STATE_IDLE, STATE_UP_DOWN, STATE_SEEDING, STATE_DOWNLOADING],
        value_fn=get_state,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_SPEED,
        translation_key="download_speed",
        icon="mdi:cloud-download",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        value_fn=lambda coordinator: float(
            coordinator.data["server_state"]["dl_info_speed"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_UPLOAD_SPEED,
        translation_key="upload_speed",
        icon="mdi:cloud-upload",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        value_fn=lambda coordinator: float(
            coordinator.data["server_state"]["up_info_speed"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_ALL_TORRENTS,
        translation_key="all_torrents",
        native_unit_of_measurement="torrents",
        value_fn=lambda coordinator: count_torrents_in_states(coordinator, []),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_ACTIVE_TORRENTS,
        translation_key="active_torrents",
        native_unit_of_measurement="torrents",
        value_fn=lambda coordinator: count_torrents_in_states(
            coordinator, ["downloading", "uploading"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_INACTIVE_TORRENTS,
        translation_key="inactive_torrents",
        native_unit_of_measurement="torrents",
        value_fn=lambda coordinator: count_torrents_in_states(
            coordinator, ["stalledDL", "stalledUP"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_PAUSED_TORRENTS,
        translation_key="paused_torrents",
        native_unit_of_measurement="torrents",
        value_fn=lambda coordinator: count_torrents_in_states(
            coordinator, ["pausedDL", "pausedUP"]
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up qBittorrent sensor entries."""

    coordinator: QBittorrentDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        QBittorrentSensor(coordinator, config_entry, description)
        for description in SENSOR_TYPES
    )


class QBittorrentSensor(CoordinatorEntity[QBittorrentDataCoordinator], SensorEntity):
    """Representation of a qBittorrent sensor."""

    _attr_has_entity_name = True
    entity_description: QBittorrentSensorEntityDescription

    def __init__(
        self,
        coordinator: QBittorrentDataCoordinator,
        config_entry: ConfigEntry,
        entity_description: QBittorrentSensorEntityDescription,
    ) -> None:
        """Initialize the qBittorrent sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{config_entry.entry_id}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="QBittorrent",
        )

    @property
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator)


def count_torrents_in_states(
    coordinator: QBittorrentDataCoordinator, states: list[str]
) -> int:
    """Count the number of torrents in specified states."""
    # When torrents are not in the returned data, there are none, return 0.
    if "torrents" not in coordinator.data:
        return 0

    if not states:
        return len(coordinator.data["torrents"])

    return len(
        [
            torrent
            for torrent in coordinator.data["torrents"].values()
            if torrent["state"] in states
        ]
    )
