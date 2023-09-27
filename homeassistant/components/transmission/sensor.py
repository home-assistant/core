"""Support for monitoring the Transmission BitTorrent client API."""
from __future__ import annotations

from contextlib import suppress
from typing import Any

from transmission_rpc.torrent import Torrent

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_IDLE, UnitOfDataRate
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TransmissionClient
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission sensors."""

    tm_client: TransmissionClient = hass.data[DOMAIN][config_entry.entry_id]
    name: str = config_entry.data[CONF_NAME]

    dev = [
        TransmissionSpeedSensor(
            tm_client,
            name,
            "download_speed",
            "download",
        ),
        TransmissionSpeedSensor(
            tm_client,
            name,
            "upload_speed",
            "upload",
        ),
        TransmissionStatusSensor(
            tm_client,
            name,
            "transmission_status",
            "status",
        ),
        TransmissionTorrentsSensor(
            tm_client,
            name,
            "active_torrents",
            "active_torrents",
        ),
        TransmissionTorrentsSensor(
            tm_client,
            name,
            "paused_torrents",
            "paused_torrents",
        ),
        TransmissionTorrentsSensor(
            tm_client,
            name,
            "total_torrents",
            "total_torrents",
        ),
        TransmissionTorrentsSensor(
            tm_client,
            name,
            "completed_torrents",
            "completed_torrents",
        ),
        TransmissionTorrentsSensor(
            tm_client,
            name,
            "started_torrents",
            "started_torrents",
        ),
    ]

    async_add_entities(dev, True)


class TransmissionSensor(SensorEntity):
    """A base class for all Transmission sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        tm_client: TransmissionClient,
        client_name: str,
        sensor_translation_key: str,
        key: str,
    ) -> None:
        """Initialize the sensor."""
        self._tm_client = tm_client
        self._attr_translation_key = sensor_translation_key
        self._key = key
        self._state: StateType = None
        self._attr_unique_id = f"{tm_client.config_entry.entry_id}-{key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, tm_client.config_entry.entry_id)},
            manufacturer="Transmission",
            name=client_name,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._tm_client.api.available

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._tm_client.api.signal_update, update
            )
        )


class TransmissionSpeedSensor(TransmissionSensor):
    """Representation of a Transmission speed sensor."""

    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
    _attr_suggested_display_precision = 2
    _attr_suggested_unit_of_measurement = UnitOfDataRate.MEGABYTES_PER_SECOND

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        if data := self._tm_client.api.data:
            b_spd = (
                float(data.download_speed)
                if self._key == "download"
                else float(data.upload_speed)
            )
            self._state = b_spd


class TransmissionStatusSensor(TransmissionSensor):
    """Representation of a Transmission status sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATE_IDLE, STATE_UP_DOWN, STATE_SEEDING, STATE_DOWNLOADING]

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        if data := self._tm_client.api.data:
            upload = data.upload_speed
            download = data.download_speed
            if upload > 0 and download > 0:
                self._state = STATE_UP_DOWN
            elif upload > 0 and download == 0:
                self._state = STATE_SEEDING
            elif upload == 0 and download > 0:
                self._state = STATE_DOWNLOADING
            else:
                self._state = STATE_IDLE
        else:
            self._state = None


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
            torrents=self._tm_client.api.torrents,
            order=self._tm_client.config_entry.options[CONF_ORDER],
            limit=self._tm_client.config_entry.options[CONF_LIMIT],
            statuses=self.MODES[self._key],
        )
        return {
            STATE_ATTR_TORRENT_INFO: info,
        }

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        torrents = _filter_torrents(
            self._tm_client.api.torrents, statuses=self.MODES[self._key]
        )
        self._state = len(torrents)


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
