"""Support for monitoring the Transmission BitTorrent client API."""
from __future__ import annotations

from contextlib import suppress
from typing import Any

from transmission_rpc.torrent import Torrent

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_IDLE, UnitOfDataRate
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
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
    STATE_DOWNLOADING,
    STATE_SEEDING,
    STATE_UP_DOWN,
    SUPPORTED_ORDER_MODES,
)

SPEED_SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="Down Speed",
        name="Down speed",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="Up Speed",
        name="Up speed",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]
STATUS_SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="Status",
        name="Status",
    ),
]
TORRENTS_SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="Active Torrents",
        name="Active torrents",
    ),
    SensorEntityDescription(
        key="Paused Torrents",
        name="Paused torrents",
    ),
    SensorEntityDescription(
        key="Total Torrents",
        name="Total torrents",
    ),
    SensorEntityDescription(
        key="Completed Torrents",
        name="Completed torrents",
    ),
    SensorEntityDescription(
        key="Started Torrents",
        name="Started torrents",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission sensors."""

    tm_client = hass.data[DOMAIN][config_entry.entry_id]
    client_name = config_entry.data[CONF_NAME]

    dev = [
        *[
            TransmissionSpeedSensor(description, tm_client, client_name)
            for description in SPEED_SENSOR_DESCRIPTIONS
        ],
        *[
            TransmissionStatusSensor(description, tm_client, client_name)
            for description in STATUS_SENSOR_DESCRIPTIONS
        ],
        *[
            TransmissionTorrentsSensor(description, tm_client, client_name)
            for description in TORRENTS_SENSOR_DESCRIPTIONS
        ],
    ]

    async_add_entities(dev, True)


class TransmissionSensor(SensorEntity):
    """A base class for all Transmission sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entity_description: SensorEntityDescription,
        tm_client: TransmissionClient,
        client_name: str,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = entity_description
        self._tm_client: TransmissionClient = tm_client
        self._state: Any | None = None

        self._attr_unique_id = f"{client_name} {self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
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
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
    _attr_suggested_display_precision = 2
    _attr_suggested_unit_of_measurement = UnitOfDataRate.MEGABYTES_PER_SECOND

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        if data := self._tm_client.api.data:
            b_spd = (
                float(data.download_speed)
                if self.entity_description.key == "Down Speed"
                else float(data.upload_speed)
            )
            self._state = b_spd


class TransmissionStatusSensor(TransmissionSensor):
    """Representation of a Transmission status sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATE_IDLE, STATE_UP_DOWN, STATE_SEEDING, STATE_DOWNLOADING]
    _attr_translation_key = "transmission_status"

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

    MODES = {
        "Started Torrents": ("downloading"),
        "Completed Torrents": ("seeding"),
        "Paused Torrents": ("stopped"),
        "Active Torrents": ("seeding", "downloading"),
        "Total Torrents": None,
    }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes, if any."""
        info = _torrents_info(
            torrents=self._tm_client.api.torrents,
            order=self._tm_client.config_entry.options[CONF_ORDER],
            limit=self._tm_client.config_entry.options[CONF_LIMIT],
            statuses=self.MODES[self.entity_description.key],
        )
        return {
            STATE_ATTR_TORRENT_INFO: info,
        }

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        torrents = _filter_torrents(
            self._tm_client.api.torrents,
            statuses=self.MODES[self.entity_description.key],
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
            "added_date": torrent.date_added,
            "percent_done": f"{torrent.percent_done * 100:.2f}",
            "status": torrent.status,
            "id": torrent.id,
        }
        with suppress(ValueError):
            info["eta"] = str(torrent.eta)
    return infos
