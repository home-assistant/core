"""Support for monitoring the Transmission BitTorrent client API."""
from __future__ import annotations

from contextlib import suppress
from typing import Any

from transmissionrpc.torrent import Torrent

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    DATA_RATE_MEGABYTES_PER_SECOND,
    STATE_IDLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TransmissionClientCoordinator
from .const import (
    CONF_LIMIT,
    CONF_ORDER,
    DOMAIN,
    STATE_ATTR_TORRENT_INFO,
    SUPPORTED_ORDER_MODES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission sensors."""

    tm_client: TransmissionClientCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        TransmissionSpeedSensor(tm_client, "Down Speed", "download"),
        TransmissionSpeedSensor(tm_client, "Up Speed", "upload"),
        TransmissionStatusSensor(tm_client, "Status", ""),
        TransmissionTorrentsSensor(tm_client, "Active Torrents", "active"),
        TransmissionTorrentsSensor(tm_client, "Paused Torrents", "paused"),
        TransmissionTorrentsSensor(tm_client, "Total Torrents", "total"),
        TransmissionTorrentsSensor(tm_client, "Completed Torrents", "completed"),
        TransmissionTorrentsSensor(tm_client, "Started Torrents", "started"),
    ]

    async_add_entities(entities)


class TransmissionSensor(CoordinatorEntity, SensorEntity):
    """A base class for all Transmission sensors."""

    coordinator: TransmissionClientCoordinator

    def __init__(
        self,
        coordinator: TransmissionClientCoordinator,
        sensor_name: str,
        sub_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        client_name = self.coordinator.config_entry.data[CONF_NAME]
        self._sub_type = sub_type
        self._attr_name = f"{client_name} {sensor_name}"
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.data[CONF_HOST]}-{self.name}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.data[CONF_HOST])},
            "default_name": client_name,
            "entry_type": "service",
        }


class TransmissionSpeedSensor(TransmissionSensor):
    """Representation of a Transmission speed sensor."""

    _attr_native_unit_of_measurement = DATA_RATE_MEGABYTES_PER_SECOND

    @property
    def native_value(self) -> float:
        """Return the state of the entity."""
        data = self.coordinator.data
        mb_spd = (
            float(data.downloadSpeed)
            if self._sub_type == "download"
            else float(data.uploadSpeed)
        )
        mb_spd = mb_spd / 1024 / 1024
        return round(mb_spd, 2 if mb_spd < 0.1 else 1)


class TransmissionStatusSensor(TransmissionSensor):
    """Representation of a Transmission status sensor."""

    @property
    def native_value(self) -> str:
        """Return the state of the entity."""
        state = STATE_IDLE
        upload = self.coordinator.data.uploadSpeed
        download = self.coordinator.data.downloadSpeed
        if upload > 0 and download > 0:
            state = "Up/Down"
        elif upload > 0 and download == 0:
            state = "Seeding"
        elif upload == 0 and download > 0:
            state = "Downloading"
        return state


class TransmissionTorrentsSensor(TransmissionSensor):
    """Representation of a Transmission torrents sensor."""

    SUBTYPE_MODES = {
        "started": ("downloading"),
        "completed": ("seeding"),
        "paused": ("stopped"),
        "active": ("seeding", "downloading"),
        "total": None,
    }
    _attr_native_unit_of_measurement = "Torrents"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes, if any."""
        info = _torrents_info(
            torrents=self.coordinator.tm_data.torrents,
            order=self.coordinator.config_entry.options[CONF_ORDER],
            limit=self.coordinator.config_entry.options[CONF_LIMIT],
            statuses=self.SUBTYPE_MODES[self._sub_type],
        )
        return {
            STATE_ATTR_TORRENT_INFO: info,
        }

    @property
    def native_value(self) -> int:
        """Return the state of the entity."""
        torrents = _filter_torrents(
            self.coordinator.tm_data.torrents,
            statuses=self.SUBTYPE_MODES[self._sub_type],
        )
        return len(torrents)


def _filter_torrents(torrents: list[Torrent], statuses=None) -> list[Torrent]:
    return [
        torrent
        for torrent in torrents
        if statuses is None or torrent.status in statuses
    ]


def _torrents_info(torrents, order, limit, statuses=None) -> dict[str, dict]:
    infos = {}
    torrents = _filter_torrents(torrents, statuses)
    torrents = SUPPORTED_ORDER_MODES[order](torrents)
    for torrent in torrents[:limit]:
        info = infos[torrent.name] = {
            "added_date": torrent.addedDate,
            "percent_done": f"{torrent.percentDone * 100:.2f}",
            "status": torrent.status,
            "id": torrent.id,
        }
        with suppress(ValueError):
            info["eta"] = str(torrent.eta)
    return infos
