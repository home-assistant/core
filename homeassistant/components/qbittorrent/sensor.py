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


SPEED_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="download", translation_key="download_speed", name="Download Speed"),
    SensorEntityDescription(key="upload", translation_key="upload_speed", name="Upload Speed"),
)

STATUS_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="status", translation_key="current_status", name="Status"),
)

TORRENT_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="active_torrents", translation_key="active_torrents", name="Active Torrents"),
    SensorEntityDescription(key="inactive_torrents", translation_key="inactive_torrents", name="Inactive Torrents"),
    SensorEntityDescription(key="paused_torrents", translation_key="paused_torrents", name="Paused Torrents"),
    SensorEntityDescription(key="total_torrents", translation_key="total_torrents", name="Total Torrents"),
    SensorEntityDescription(key="seeding_torrents", translation_key="seeding_torrents", name="Seeding Torrents"),
    SensorEntityDescription(key="started_torrents", translation_key="started_torrents", name="Started Torrents"),
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

    entities: list[QBittorrentSensor] = []

    entities = [
        QBittorrentSpeedSensor(coordinator, description)
        for description in SPEED_SENSORS
    ]
    entities += [
        QBittorrentStatusSensor(coordinator, description)
        for description in STATUS_SENSORS
    ]
    entities += [
        QBittorrentTorrentsSensor(coordinator, description)
        for description in TORRENT_SENSORS
    ]

    async_add_entities(entities)


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


class QBittorrentSpeedSensor(QBittorrentSensor):
    """Representation of a qBittorrent speed sensor."""

    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
    _attr_suggested_display_precision = 2
    _attr_suggested_unit_of_measurement = UnitOfDataRate.MEGABYTES_PER_SECOND

    @property
    def native_value(self) -> float:
        """Return the speed of the sensor."""
        data = self.coordinator.data
        return (
            float(data["server_state"]["dl_info_speed"])
            if self.entity_description.key == "download"
            else float(data["server_state"]["up_info_speed"])
        )
    
    
class QBittorrentStatusSensor(QBittorrentSensor):
    """Representation of a qBittorrent status sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATE_IDLE, STATE_UP_DOWN, STATE_SEEDING, STATE_DOWNLOADING]

    @property
    def native_value(self) -> str:
        """Return the value of the status sensor."""
        download = self.coordinator.data["server_state"]["dl_info_speed"]
        upload = self.coordinator.data["server_state"]["up_info_speed"]
        if upload > 0 and download > 0:
            return STATE_UP_DOWN
        if upload > 0 and download == 0:
            return STATE_SEEDING
        if upload == 0 and download > 0:
            return STATE_DOWNLOADING
        return STATE_IDLE


class QBittorrentTorrentsSensor(QBittorrentSensor):
    """Representation of a qBittorrent torrents sensor."""

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return "Torrents"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes, if any."""
        info = format_torrents(
            getattr(self.coordinator, self.entity_description.key)
        )
        return {
            STATE_ATTR_TORRENT_INFO: info,
        }

    @property
    def native_value(self) -> int:
        """Return the count of the sensor."""
        torrents = format_torrents(
            getattr(self.coordinator, self.entity_description.key)
        )
        return len(torrents)


def seconds_to_hhmmss(seconds):
    """Convert seconds to HH:MM:SS format."""
    if seconds == 8640000:
        return 'None'
    else:
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))


def format_unix_timestamp(timestamp):
    """Format a UNIX timestamp to a human-readable date."""
    dt_object = datetime.utcfromtimestamp(timestamp).replace(tzinfo=timezone.utc)
    formatted_date = dt_object.strftime("%Y-%m-%dT%H:%M:%S%z")
    return formatted_date


def format_progress(torrent):
    """Format the progress of a torrent."""
    progress = torrent["progress"]
    progress = float(progress) * 100
    progress = '{:.2f}'.format(progress)

    return progress


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


def format_torrents(torrents: dict[str, Any]):
    """Format a list of torrents."""
    value = {}
    for torrent in torrents:
        value[torrent["name"]] = format_torrent(torrent)

    return value


def format_torrent(torrent):
    """Format a single torrent."""
    value = {}
    value['id'] = torrent["hash"]
    value['added_date'] = format_unix_timestamp(torrent["added_on"])
    value['percent_done'] = format_progress(torrent)
    value['status'] = torrent["state"]
    value['eta'] = seconds_to_hhmmss(torrent["eta"])
    value['ratio'] = '{:.2f}'.format(float(torrent["ratio"]))

    return value