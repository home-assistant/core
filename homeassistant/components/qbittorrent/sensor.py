"""Support for monitoring the qBittorrent API."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CREATE_TORRENT_SENSORS, DOMAIN, QBITTORRENT_TORRENT_STATES
from .coordinator import QBittorrentDataCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_CURRENT_STATUS = "current_status"
SENSOR_TYPE_DOWNLOAD_SPEED = "download_speed"
SENSOR_TYPE_UPLOAD_SPEED = "upload_speed"

SENSOR_TYPE_TORRENTS = "torrents"
SENSOR_TYPE_TORRENTS_DOWNLOADING = "torrents_downloading"
SENSOR_TYPE_TORRENTS_UPLOADING = "torrents_uploading"
SENSOR_TYPE_TORRENTS_STALLED = "torrents_stalled"
SENSOR_TYPE_TORRENTS_STOPPED = "torrents_stopped"
SENSOR_TYPE_TORRENTS_COMPLETED = "torrents_completed"
SENSOR_TYPE_TORRENTS_QUEUED = "torrents_queued"
SENSOR_TYPE_TORRENTS_CHECKING = "torrents_checking"
SENSOR_TYPE_TORRENTS_ERROR = "torrents_error"


@dataclass
class QBittorrentMixin:
    """Mixin for required keys."""

    value_fn: Callable[[dict[str, Any]], StateType]
    attrs_fn: Callable[[dict[str, Any]], Mapping[str, Any]] | None


@dataclass
class QBittorrentSensorEntityDescription(SensorEntityDescription, QBittorrentMixin):
    """Describes QBittorrent sensor entity."""


def _get_qbittorrent_state(data: dict[str, Any]) -> str:
    download = data["server_state"]["dl_info_speed"]
    upload = data["server_state"]["up_info_speed"]

    if upload > 0 and download > 0:
        return "up_down"
    if upload > 0 and download == 0:
        return "seeding"
    if upload == 0 and download > 0:
        return "downloading"
    return STATE_IDLE


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


def count_torrents(data: dict[str, Any], filter_state=None) -> int:
    """Return the count of torrents which match the given set of state filters."""
    torrents = data["torrents"]

    count = 0
    for torrent in torrents.values():
        if not filter_state or torrent["state"] in filter_state:
            count += 1

    return count


def list_torrents(data: dict[str, Any], filter_state=None) -> Mapping[str, Any]:
    """Return a map from torrent name to the torrent's status, for torrents matching the given state filter."""
    torrents = data["torrents"]
    attrs: Mapping[str, Any] = {"torrent_names": []}

    for torrent in torrents.values():
        if not filter_state or torrent["state"] in filter_state:
            torrent_name = torrent["name"]
            attrs["torrent_names"].append(torrent_name)

    return attrs


BASE_SENSOR_TYPES: tuple[QBittorrentSensorEntityDescription, ...] = (
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_CURRENT_STATUS,
        name="Status",
        value_fn=_get_qbittorrent_state,
        attrs_fn=None,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_SPEED,
        name="Down Speed",
        icon="mdi:cloud-download",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: format_speed(data["server_state"]["dl_info_speed"]),
        attrs_fn=None,
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_UPLOAD_SPEED,
        name="Up Speed",
        icon="mdi:cloud-upload",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: format_speed(data["server_state"]["up_info_speed"]),
        attrs_fn=None,
    ),
)


TORRENT_SENSOR_TYPES: tuple[QBittorrentSensorEntityDescription, ...] = (
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_TORRENTS,
        name="Torrents",
        icon="mdi:cog-transfer",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: count_torrents(data, None),
        attrs_fn=lambda data: list_torrents(data, None),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_TORRENTS_DOWNLOADING,
        name="Torrents Downloading",
        icon="mdi:cloud-arrow-down",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: count_torrents(
            data, QBITTORRENT_TORRENT_STATES["downloading"]
        ),
        attrs_fn=lambda data: list_torrents(
            data, QBITTORRENT_TORRENT_STATES["downloading"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_TORRENTS_UPLOADING,
        name="Torrents Uploading",
        icon="mdi:cloud-arrow-up",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: count_torrents(
            data, QBITTORRENT_TORRENT_STATES["uploading"]
        ),
        attrs_fn=lambda data: list_torrents(
            data, QBITTORRENT_TORRENT_STATES["uploading"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_TORRENTS_STALLED,
        name="Torrents Stalled",
        icon="mdi:cloud-minus",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: count_torrents(
            data, QBITTORRENT_TORRENT_STATES["stalled"]
        ),
        attrs_fn=lambda data: list_torrents(
            data, QBITTORRENT_TORRENT_STATES["stalled"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_TORRENTS_STOPPED,
        name="Torrents Stopped",
        icon="mdi:cloud-cancel",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: count_torrents(
            data, QBITTORRENT_TORRENT_STATES["stopped"]
        ),
        attrs_fn=lambda data: list_torrents(
            data, QBITTORRENT_TORRENT_STATES["stopped"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_TORRENTS_COMPLETED,
        name="Torrents Completed",
        icon="mdi:cloud-check",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: count_torrents(
            data, QBITTORRENT_TORRENT_STATES["completed"]
        ),
        attrs_fn=lambda data: list_torrents(
            data, QBITTORRENT_TORRENT_STATES["completed"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_TORRENTS_QUEUED,
        name="Torrents Queued",
        icon="mdi:cloud-clock",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: count_torrents(
            data, QBITTORRENT_TORRENT_STATES["queued"]
        ),
        attrs_fn=lambda data: list_torrents(data, QBITTORRENT_TORRENT_STATES["queued"]),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_TORRENTS_CHECKING,
        name="Torrents Checking",
        icon="mdi:cloud-sync",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: count_torrents(
            data, QBITTORRENT_TORRENT_STATES["checking"]
        ),
        attrs_fn=lambda data: list_torrents(
            data, QBITTORRENT_TORRENT_STATES["checking"]
        ),
    ),
    QBittorrentSensorEntityDescription(
        key=SENSOR_TYPE_TORRENTS_ERROR,
        name="Torrents Erroring",
        icon="mdi:cloud-remove",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: count_torrents(data, QBITTORRENT_TORRENT_STATES["error"]),
        attrs_fn=lambda data: list_torrents(data, QBITTORRENT_TORRENT_STATES["error"]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entites: AddEntitiesCallback,
) -> None:
    """Set up qBittorrent sensor entries."""
    coordinator: QBittorrentDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        QBittorrentSensor(description, coordinator, config_entry)
        for description in BASE_SENSOR_TYPES
    ]

    if config_entry.options.get(CONF_CREATE_TORRENT_SENSORS):
        entities += [
            QBittorrentSensor(description, coordinator, config_entry)
            for description in TORRENT_SENSOR_TYPES
        ]

    async_add_entites(entities)


class QBittorrentSensor(CoordinatorEntity[QBittorrentDataCoordinator], SensorEntity):
    """Representation of a qBittorrent sensor."""

    entity_description: QBittorrentSensorEntityDescription

    def __init__(
        self,
        description: QBittorrentSensorEntityDescription,
        coordinator: QBittorrentDataCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the qBittorrent sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}-{description.key}"
        self._attr_name = f"{config_entry.title} {description.name}"
        self._attr_available = False

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes for torrent statistics sensors."""
        if self.entity_description.attrs_fn:
            return self.entity_description.attrs_fn(self.coordinator.data)

        return None
