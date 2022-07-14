"""Support for monitoring the Transmission BitTorrent client API."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from transmission_rpc.torrent import Torrent

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_IDLE, UnitOfDataRate, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TransmissionClient
from .const import (
    CONF_LIMIT,
    CONF_ORDER,
    DOMAIN,
    STATE_ATTR_TORRENT_INFO,
    SUPPORTED_ORDER_MODES,
)


@dataclass
class TransmissionSensorEntityDescription(SensorEntityDescription):
    """Describe Transmission sensor entity."""

    sub_type: str | None = None


SPEED_SENSOR_DESCRIPTIONS = [
    TransmissionSensorEntityDescription(
        key="download",
        name="Down speed",
        sub_type="download",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TransmissionSensorEntityDescription(
        key="upload",
        name="Up speed",
        sub_type="upload",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]
STATUS_SENSOR_DESCRIPTIONS = [
    TransmissionSensorEntityDescription(
        key="status",
        name="Status",
    ),
]
TORRENTS_SENSOR_DESCRIPTIONS = [
    TransmissionSensorEntityDescription(
        key="active_torrents",
        name="Active torrents",
        sub_type="active",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TransmissionSensorEntityDescription(
        key="paused_torrents",
        name="Paused torrents",
        sub_type="paused",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TransmissionSensorEntityDescription(
        key="total_torrents",
        name="Total torrents",
        sub_type="total",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TransmissionSensorEntityDescription(
        key="completed_torrents",
        name="Completed torrents",
        sub_type="completed",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TransmissionSensorEntityDescription(
        key="started_torrents",
        name="Started torrents",
        sub_type="started",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


def get_unique_id(
    config_entry: ConfigEntry, entity_description: TransmissionSensorEntityDescription
) -> str:
    """Generate a unique id for entity."""
    return f"{config_entry.entry_id}-{entity_description.key}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission sensors."""

    tm_client = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]

    dev = [
        *[
            TransmissionSpeedSensor(tm_client, name, description)
            for description in SPEED_SENSOR_DESCRIPTIONS
        ],
        *[
            TransmissionStatusSensor(tm_client, name, description)
            for description in STATUS_SENSOR_DESCRIPTIONS
        ],
        *[
            TransmissionTorrentsSensor(tm_client, name, description)
            for description in TORRENTS_SENSOR_DESCRIPTIONS
        ],
    ]

    async_add_entities(dev, True)


class TransmissionSensor(SensorEntity):
    """A base class for all Transmission sensors."""

    entity_description: TransmissionSensorEntityDescription

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        tm_client: TransmissionClient,
        client_name: str,
        entity_description: TransmissionSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = entity_description
        self._tm_client = tm_client
        self._state = None
        self._attr_unique_id = (
            f"{tm_client.config_entry.entry_id}-{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tm_client.config_entry.entry_id)},
            manufacturer="Transmission",
            name=client_name,
        )

    @property
    def native_value(self) -> StateType | None:
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
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABYTES_PER_SECOND

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        if data := self._tm_client.api.data:
            mb_spd = (
                float(data.downloadSpeed)
                if self.entity_description.sub_type == "download"
                else float(data.uploadSpeed)
            )
            mb_spd = mb_spd / 1024 / 1024
            self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)


class TransmissionStatusSensor(TransmissionSensor):
    """Representation of a Transmission status sensor."""

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        if data := self._tm_client.api.data:
            upload = data.uploadSpeed
            download = data.downloadSpeed
            if upload > 0 and download > 0:
                self._state = "Up/Down"
            elif upload > 0 and download == 0:
                self._state = "Seeding"
            elif upload == 0 and download > 0:
                self._state = "Downloading"
            else:
                self._state = STATE_IDLE
        else:
            self._state = None


class TransmissionTorrentsSensor(TransmissionSensor):
    """Representation of a Transmission torrents sensor."""

    SUBTYPE_MODES = {
        "started": ("downloading"),
        "completed": ("seeding"),
        "paused": ("stopped"),
        "active": ("seeding", "downloading"),
        "total": None,
    }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes, if any."""
        info = _torrents_info(
            torrents=self._tm_client.api.torrents,
            order=self._tm_client.config_entry.options[CONF_ORDER],
            limit=self._tm_client.config_entry.options[CONF_LIMIT],
            statuses=self.SUBTYPE_MODES[self.entity_description.sub_type],
        )
        return {
            STATE_ATTR_TORRENT_INFO: info,
        }

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        torrents = _filter_torrents(
            self._tm_client.api.torrents,
            statuses=self.SUBTYPE_MODES[self.entity_description.sub_type],
        )
        self._state = len(torrents)


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
