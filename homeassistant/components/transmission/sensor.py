"""Support for monitoring the Transmission BitTorrent client API."""
from __future__ import annotations

from contextlib import suppress
from typing import Any

from transmission_rpc.session import SessionStats
from transmission_rpc.torrent import Torrent

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_IDLE, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_LIMIT,
    CONF_ORDER,
    DOMAIN,
    STATE_ATTR_TORRENT_INFO,
    STATE_DOWNLOADING,
    STATE_SEEDING,
    STATE_UP_DOWN,
    SUPPORTED_ORDER_MODES,
)
from .coordinator import TransmissionDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission sensors."""

    coordinator: TransmissionDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    name: str = config_entry.data[CONF_NAME]

    dev = [
        TransmissionSpeedSensor(
            coordinator,
            name,
            "download_speed",
            "download",
        ),
        TransmissionSpeedSensor(
            coordinator,
            name,
            "upload_speed",
            "upload",
        ),
        TransmissionStatusSensor(
            coordinator,
            name,
            "transmission_status",
            "status",
        ),
        TransmissionTorrentsSensor(
            coordinator,
            name,
            "active_torrents",
            "active_torrents",
        ),
        TransmissionTorrentsSensor(
            coordinator,
            name,
            "paused_torrents",
            "paused_torrents",
        ),
        TransmissionTorrentsSensor(
            coordinator,
            name,
            "total_torrents",
            "total_torrents",
        ),
        TransmissionTorrentsSensor(
            coordinator,
            name,
            "completed_torrents",
            "completed_torrents",
        ),
        TransmissionTorrentsSensor(
            coordinator,
            name,
            "started_torrents",
            "started_torrents",
        ),
    ]

    async_add_entities(dev, True)


class TransmissionSensor(CoordinatorEntity[SessionStats], SensorEntity):
    """A base class for all Transmission sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: TransmissionDataUpdateCoordinator,
        client_name: str,
        sensor_translation_key: str,
        key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_translation_key = sensor_translation_key
        self._key = key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Transmission",
            name=client_name,
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
            if self._key == "download"
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
            torrents=self.coordinator.api.torrents,
            order=self.coordinator.config_entry.options[CONF_ORDER],
            limit=self.coordinator.config_entry.options[CONF_LIMIT],
            statuses=self.MODES[self._key],
        )
        return {
            STATE_ATTR_TORRENT_INFO: info,
        }

    @property
    def native_value(self) -> int:
        """Return the count of the sensor."""
        torrents = _filter_torrents(
            self.coordinator.api.torrents, statuses=self.MODES[self._key]
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
            "added_date": torrent.date_added,
            "percent_done": f"{torrent.percent_done * 100:.2f}",
            "status": torrent.status,
            "id": torrent.id,
        }
        with suppress(ValueError):
            info["eta"] = str(torrent.eta)
    return infos
