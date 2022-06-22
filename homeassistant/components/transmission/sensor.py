"""Support for monitoring the Transmission BitTorrent client API."""
from __future__ import annotations

from contextlib import suppress

from transmissionrpc.torrent import Torrent

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_IDLE, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_LIMIT,
    CONF_ORDER,
    DOMAIN,
    STATE_ATTR_TORRENT_INFO,
    SUPPORTED_ORDER_MODES,
)
from .coordinator import TransmissionDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission sensors."""

    tm_client: TransmissionDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    name = config_entry.data[CONF_NAME]

    entities = [
        TransmissionSpeedSensor(tm_client, name, "Down Speed", "download"),
        TransmissionSpeedSensor(tm_client, name, "Up Speed", "upload"),
        TransmissionStatusSensor(tm_client, name, "Status"),
        TransmissionTorrentsSensor(tm_client, name, "Active Torrents", "active"),
        TransmissionTorrentsSensor(tm_client, name, "Paused Torrents", "paused"),
        TransmissionTorrentsSensor(tm_client, name, "Total Torrents", "total"),
        TransmissionTorrentsSensor(tm_client, name, "Completed Torrents", "completed"),
        TransmissionTorrentsSensor(tm_client, name, "Started Torrents", "started"),
    ]

    async_add_entities(entities)


class TransmissionSensor(
    CoordinatorEntity[TransmissionDataUpdateCoordinator], SensorEntity
):
    """A base class for all Transmission sensors."""

    def __init__(
        self,
        tm_client,
        client_name,
        sensor_name,
        sub_type="",
    ):
        """Initialize the sensor."""
        super().__init__(tm_client)
        self._sub_type = sub_type
        self._attr_name = f"{client_name} {sensor_name}"
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.data[CONF_HOST]}-{self.name}"
        )
        self._state = None


class TransmissionSpeedSensor(TransmissionSensor):
    """Representation of a Transmission speed sensor."""

    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABYTES_PER_SECOND

    @property
    def native_value(self):
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
    def native_value(self):
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
    def extra_state_attributes(self):
        """Return the state attributes, if any."""
        info = _torrents_info(
            torrents=self.coordinator.api.torrents,
            order=self.coordinator.config_entry.options[CONF_ORDER],
            limit=self.coordinator.config_entry.options[CONF_LIMIT],
            statuses=self.SUBTYPE_MODES[self._sub_type],
        )
        return {
            STATE_ATTR_TORRENT_INFO: info,
        }

    @property
    def native_value(self):
        """Return the state of the entity."""
        torrents = _filter_torrents(
            self.coordinator.api.torrents,
            statuses=self.SUBTYPE_MODES[self._sub_type],
        )
        return len(torrents)


def _filter_torrents(torrents: list[Torrent], statuses=None) -> list[Torrent]:
    return [
        torrent
        for torrent in torrents
        if statuses is None or torrent.status in statuses
    ]


def _torrents_info(torrents, order, limit, statuses=None):
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
