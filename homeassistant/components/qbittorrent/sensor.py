"""Support for monitoring the qBittorrent API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, UnitOfDataRate, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATE_DOWNLOADING, STATE_SEEDING, STATE_UP_DOWN
from .coordinator import QBittorrentDataCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_CURRENT_STATUS = "current_status"
SENSOR_TYPE_CONNECTION_STATUS = "connection_status"
SENSOR_TYPE_DOWNLOAD_SPEED = "download_speed"
SENSOR_TYPE_UPLOAD_SPEED = "upload_speed"
SENSOR_TYPE_DOWNLOAD_SPEED_LIMIT = "download_speed_limit"
SENSOR_TYPE_UPLOAD_SPEED_LIMIT = "upload_speed_limit"
SENSOR_TYPE_ALLTIME_DOWNLOAD = "alltime_download"
SENSOR_TYPE_ALLTIME_UPLOAD = "alltime_upload"
SENSOR_TYPE_GLOBAL_RATIO = "global_ratio"
SENSOR_TYPE_ALL_TORRENTS = "all_torrents"
SENSOR_TYPE_PAUSED_TORRENTS = "paused_torrents"
SENSOR_TYPE_ACTIVE_TORRENTS = "active_torrents"
SENSOR_TYPE_INACTIVE_TORRENTS = "inactive_torrents"


def get_state(coordinator: QBittorrentDataCoordinator) -> str:
    """Get current download/upload state."""
    server_state = cast(Mapping, coordinator.data.get("server_state"))
    upload = cast(int, server_state.get("up_info_speed"))
    download = cast(int, server_state.get("dl_info_speed"))

    if upload > 0 and download > 0:
        return STATE_UP_DOWN
    if upload > 0 and download == 0:
        return STATE_SEEDING
    if upload == 0 and download > 0:
        return STATE_DOWNLOADING
    return STATE_IDLE


def get_connection_status(coordinator: QBittorrentDataCoordinator) -> str:
    """Get current download/upload state."""
    server_state = cast(Mapping, coordinator.data.get("server_state"))
    return cast(str, server_state.get("connection_status"))


def get_download_speed(coordinator: QBittorrentDataCoordinator) -> int:
    """Get current download speed."""
    server_state = cast(Mapping, coordinator.data.get("server_state"))
    return cast(int, server_state.get("dl_info_speed"))


def get_upload_speed(coordinator: QBittorrentDataCoordinator) -> int:
    """Get current upload speed."""
    server_state = cast(Mapping[str, Any], coordinator.data.get("server_state"))
    return cast(int, server_state.get("up_info_speed"))


def get_download_speed_limit(coordinator: QBittorrentDataCoordinator) -> int:
    """Get current download speed."""
    server_state = cast(Mapping, coordinator.data.get("server_state"))
    return cast(int, server_state.get("dl_rate_limit"))


def get_upload_speed_limit(coordinator: QBittorrentDataCoordinator) -> int:
    """Get current upload speed."""
    server_state = cast(Mapping[str, Any], coordinator.data.get("server_state"))
    return cast(int, server_state.get("up_rate_limit"))


def get_alltime_download(coordinator: QBittorrentDataCoordinator) -> int:
    """Get current download speed."""
    server_state = cast(Mapping, coordinator.data.get("server_state"))
    return cast(int, server_state.get("alltime_dl"))


def get_alltime_upload(coordinator: QBittorrentDataCoordinator) -> int:
    """Get current download speed."""
    server_state = cast(Mapping, coordinator.data.get("server_state"))
    return cast(int, server_state.get("alltime_ul"))


def get_global_ratio(coordinator: QBittorrentDataCoordinator) -> float:
    """Get current download speed."""
    server_state = cast(Mapping, coordinator.data.get("server_state"))
    return cast(float, server_state.get("global_ratio"))


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
        key=SENSOR_TYPE_CONNECTION_STATUS,
        translation_key="connection_status",
        device_class=SensorDeviceClass.ENUM,
        options=["connected", "firewalled", "disconnected"],
        value_fn=get_connection_status,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_SPEED,
        translation_key="download_speed",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        value_fn=get_download_speed,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_UPLOAD_SPEED,
        translation_key="upload_speed",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        value_fn=get_upload_speed,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_SPEED_LIMIT,
        translation_key="download_speed_limit",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        value_fn=get_download_speed_limit,
        entity_registry_enabled_default=False,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_UPLOAD_SPEED_LIMIT,
        translation_key="upload_speed_limit",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        value_fn=get_upload_speed_limit,
        entity_registry_enabled_default=False,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_ALLTIME_DOWNLOAD,
        translation_key="alltime_download",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.TEBIBYTES,
        value_fn=get_alltime_download,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_ALLTIME_UPLOAD,
        translation_key="alltime_upload",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement="B",
        suggested_display_precision=2,
        suggested_unit_of_measurement="TiB",
        value_fn=get_alltime_upload,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_GLOBAL_RATIO,
        translation_key="global_ratio",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_global_ratio,
        entity_registry_enabled_default=False,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_ALL_TORRENTS,
        translation_key="all_torrents",
        value_fn=lambda coordinator: count_torrents_in_states(coordinator, []),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_ACTIVE_TORRENTS,
        translation_key="active_torrents",
        value_fn=lambda coordinator: count_torrents_in_states(
            coordinator, ["downloading", "uploading"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_INACTIVE_TORRENTS,
        translation_key="inactive_torrents",
        value_fn=lambda coordinator: count_torrents_in_states(
            coordinator, ["stalledDL", "stalledUP"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_PAUSED_TORRENTS,
        translation_key="paused_torrents",
        value_fn=lambda coordinator: count_torrents_in_states(
            coordinator, ["stoppedDL", "stoppedUP"]
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
    try:
        torrents = cast(Mapping[str, Mapping], coordinator.data.get("torrents"))
        if torrents is None:
            return 0

        if not states:
            return len(torrents)

        return len(
            [torrent for torrent in torrents.values() if torrent.get("state") in states]
        )
    except AttributeError:
        return 0
