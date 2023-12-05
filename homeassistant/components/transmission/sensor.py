"""Support for monitoring the Transmission BitTorrent client API."""
from __future__ import annotations

from contextlib import suppress
from typing import Any

from transmission_rpc.torrent import Torrent

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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    STATE_ATTR_TORRENT_INFO,
    STATE_DOWNLOADING,
    STATE_SEEDING,
    STATE_UP_DOWN,
    SUPPORTED_ORDER_MODES,
)
from .coordinator import TransmissionDataUpdateCoordinator

SPEED_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="download", translation_key="download_speed"),
    SensorEntityDescription(key="upload", translation_key="upload_speed"),
)

STATUS_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="status", translation_key="transmission_status"),
)

TORRENT_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="active_torrents", translation_key="active_torrents"),
    SensorEntityDescription(key="paused_torrents", translation_key="paused_torrents"),
    SensorEntityDescription(key="total_torrents", translation_key="total_torrents"),
    SensorEntityDescription(
        key="completed_torrents", translation_key="completed_torrents"
    ),
    SensorEntityDescription(key="started_torrents", translation_key="started_torrents"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission sensors."""

    coordinator: TransmissionDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[TransmissionSensor] = []

    entities = [
        TransmissionSpeedSensor(coordinator, description)
        for description in SPEED_SENSORS
    ]
    entities += [
        TransmissionStatusSensor(coordinator, description)
        for description in STATUS_SENSORS
    ]
    entities += [
        TransmissionTorrentsSensor(coordinator, description)
        for description in TORRENT_SENSORS
    ]

    async_add_entities(entities)


class TransmissionSensor(
    CoordinatorEntity[TransmissionDataUpdateCoordinator], SensorEntity
):
    """A base class for all Transmission sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TransmissionDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Transmission",
        )


class TransmissionSpeedSensor(TransmissionSensor):
    """Representation of a Transmission speed sensor."""

    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
    _attr_suggested_display_precision = 2
    _attr_suggested_unit_of_measurement = UnitOfDataRate.MEGABYTES_PER_SECOND

    @property
    def native_value(self) -> float:
        """Return the speed of the sensor."""
        data = self.coordinator.data
        return (
            float(data.download_speed)
            if self.entity_description.key == "download"
            else float(data.upload_speed)
        )


class TransmissionStatusSensor(TransmissionSensor):
    """Representation of a Transmission status sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATE_IDLE, STATE_UP_DOWN, STATE_SEEDING, STATE_DOWNLOADING]

    @property
    def native_value(self) -> str:
        """Return the value of the status sensor."""
        upload = self.coordinator.data.upload_speed
        download = self.coordinator.data.download_speed
        if upload > 0 and download > 0:
            return STATE_UP_DOWN
        if upload > 0 and download == 0:
            return STATE_SEEDING
        if upload == 0 and download > 0:
            return STATE_DOWNLOADING
        return STATE_IDLE


class TransmissionTorrentsSensor(TransmissionSensor):
    """Representation of a Transmission torrents sensor."""

    MODES: dict[str, list[str] | None] = {
        "started_torrents": ["downloading"],
        "completed_torrents": ["seeding"],
        "paused_torrents": ["stopped"],
        "active_torrents": [
            "seeding",
            "downloading",
        ],
        "total_torrents": None,
    }

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return "Torrents"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes, if any."""
        info = _torrents_info(
            torrents=self.coordinator.torrents,
            order=self.coordinator.order,
            limit=self.coordinator.limit,
            statuses=self.MODES[self.entity_description.key],
        )
        return {
            STATE_ATTR_TORRENT_INFO: info,
        }

    @property
    def native_value(self) -> int:
        """Return the count of the sensor."""
        torrents = _filter_torrents(
            self.coordinator.torrents, statuses=self.MODES[self.entity_description.key]
        )
        return len(torrents)


def _filter_torrents(
    torrents: list[Torrent], statuses: list[str] | None = None
) -> list[Torrent]:
    return [
        torrent
        for torrent in torrents
        if statuses is None or torrent.status in statuses
    ]


def _torrents_info(
    torrents: list[Torrent], order: str, limit: int, statuses: list[str] | None = None
) -> dict[str, Any]:
    infos = {}
    torrents = _filter_torrents(torrents, statuses)
    torrents = SUPPORTED_ORDER_MODES[order](torrents)
    for torrent in torrents[:limit]:
        info = infos[torrent.name] = {
            "added_date": torrent.added_date,
            "percent_done": f"{torrent.percent_done * 100:.2f}",
            "status": torrent.status,
            "id": torrent.id,
        }
        with suppress(ValueError):
            info["eta"] = str(torrent.eta)
    return infos
