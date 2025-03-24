"""Support for monitoring the Transmission BitTorrent client API."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from transmission_rpc.torrent import Torrent

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import STATE_IDLE, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    STATE_ATTR_TORRENT_INFO,
    STATE_DOWNLOADING,
    STATE_SEEDING,
    STATE_UP_DOWN,
    SUPPORTED_ORDER_MODES,
)
from .coordinator import TransmissionConfigEntry, TransmissionDataUpdateCoordinator

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


@dataclass(frozen=True, kw_only=True)
class TransmissionSensorEntityDescription(SensorEntityDescription):
    """Entity description class for Transmission sensors."""

    val_func: Callable[[TransmissionDataUpdateCoordinator], StateType]
    extra_state_attr_func: Callable[[Any], dict[str, str]] | None = None


SENSOR_TYPES: tuple[TransmissionSensorEntityDescription, ...] = (
    TransmissionSensorEntityDescription(
        key="download",
        translation_key="download_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        val_func=lambda coordinator: float(coordinator.data.download_speed),
    ),
    TransmissionSensorEntityDescription(
        key="upload",
        translation_key="upload_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        val_func=lambda coordinator: float(coordinator.data.upload_speed),
    ),
    TransmissionSensorEntityDescription(
        key="status",
        translation_key="transmission_status",
        device_class=SensorDeviceClass.ENUM,
        options=[STATE_IDLE, STATE_UP_DOWN, STATE_SEEDING, STATE_DOWNLOADING],
        val_func=lambda coordinator: get_state(
            coordinator.data.upload_speed, coordinator.data.download_speed
        ),
    ),
    TransmissionSensorEntityDescription(
        key="active_torrents",
        translation_key="active_torrents",
        val_func=lambda coordinator: coordinator.data.active_torrent_count,
        extra_state_attr_func=lambda coordinator: _torrents_info_attr(
            coordinator=coordinator, key="active_torrents"
        ),
    ),
    TransmissionSensorEntityDescription(
        key="paused_torrents",
        translation_key="paused_torrents",
        val_func=lambda coordinator: coordinator.data.paused_torrent_count,
        extra_state_attr_func=lambda coordinator: _torrents_info_attr(
            coordinator=coordinator, key="paused_torrents"
        ),
    ),
    TransmissionSensorEntityDescription(
        key="total_torrents",
        translation_key="total_torrents",
        val_func=lambda coordinator: coordinator.data.torrent_count,
        extra_state_attr_func=lambda coordinator: _torrents_info_attr(
            coordinator=coordinator, key="total_torrents"
        ),
    ),
    TransmissionSensorEntityDescription(
        key="completed_torrents",
        translation_key="completed_torrents",
        val_func=lambda coordinator: len(
            _filter_torrents(coordinator.torrents, MODES["completed_torrents"])
        ),
        extra_state_attr_func=lambda coordinator: _torrents_info_attr(
            coordinator=coordinator, key="completed_torrents"
        ),
    ),
    TransmissionSensorEntityDescription(
        key="started_torrents",
        translation_key="started_torrents",
        val_func=lambda coordinator: len(
            _filter_torrents(coordinator.torrents, MODES["started_torrents"])
        ),
        extra_state_attr_func=lambda coordinator: _torrents_info_attr(
            coordinator=coordinator, key="started_torrents"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TransmissionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Transmission sensors."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        TransmissionSensor(coordinator, description) for description in SENSOR_TYPES
    )


class TransmissionSensor(
    CoordinatorEntity[TransmissionDataUpdateCoordinator], SensorEntity
):
    """A base class for all Transmission sensors."""

    entity_description: TransmissionSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TransmissionDataUpdateCoordinator,
        entity_description: TransmissionSensorEntityDescription,
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


def _filter_torrents(
    torrents: list[Torrent], statuses: list[str] | None = None
) -> list[Torrent]:
    return [
        torrent
        for torrent in torrents
        if statuses is None or torrent.status in statuses
    ]


def _torrents_info_attr(
    coordinator: TransmissionDataUpdateCoordinator, key: str
) -> dict[str, Any]:
    infos = {}
    torrents = _filter_torrents(coordinator.torrents, MODES[key])
    torrents = SUPPORTED_ORDER_MODES[coordinator.order](torrents)
    for torrent in torrents[: coordinator.limit]:
        info = infos[torrent.name] = {
            "added_date": torrent.added_date,
            "percent_done": f"{torrent.percent_done * 100:.2f}",
            "status": torrent.status,
            "id": torrent.id,
        }
        with suppress(ValueError):
            info["eta"] = str(torrent.eta)
    return {STATE_ATTR_TORRENT_INFO: infos}
