"""Support for monitoring the Transmission BitTorrent client API."""
from __future__ import annotations

from contextlib import suppress

from transmissionrpc.torrent import Torrent

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, DATA_RATE_MEGABYTES_PER_SECOND, STATE_IDLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TransmissionClient
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

    tm_client = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]

    dev = [
        TransmissionSpeedSensor(tm_client, name, "Down Speed", "download"),
        TransmissionSpeedSensor(tm_client, name, "Up Speed", "upload"),
        TransmissionStatusSensor(tm_client, name, "Status"),
        TransmissionTorrentsSensor(tm_client, name, "Active Torrents", "active"),
        TransmissionTorrentsSensor(tm_client, name, "Paused Torrents", "paused"),
        TransmissionTorrentsSensor(tm_client, name, "Total Torrents", "total"),
        TransmissionTorrentsSensor(tm_client, name, "Completed Torrents", "completed"),
        TransmissionTorrentsSensor(tm_client, name, "Started Torrents", "started"),
    ]

    async_add_entities(dev, True)


class TransmissionSensor(SensorEntity):
    """A base class for all Transmission sensors."""

    _attr_should_poll = False

    def __init__(self, tm_client, client_name, sensor_name, sub_type=None):
        """Initialize the sensor."""
        self._tm_client: TransmissionClient = tm_client
        self._client_name = client_name
        self._name = sensor_name
        self._sub_type = sub_type
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._client_name} {self._name}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{self._tm_client.api.host}-{self.name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._tm_client.api.available

    async def async_added_to_hass(self):
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

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return DATA_RATE_MEGABYTES_PER_SECOND

    def update(self):
        """Get the latest data from Transmission and updates the state."""
        if data := self._tm_client.api.data:
            mb_spd = (
                float(data.downloadSpeed)
                if self._sub_type == "download"
                else float(data.uploadSpeed)
            )
            mb_spd = mb_spd / 1024 / 1024
            self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)


class TransmissionStatusSensor(TransmissionSensor):
    """Representation of a Transmission status sensor."""

    def update(self):
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
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "Torrents"

    @property
    def extra_state_attributes(self):
        """Return the state attributes, if any."""
        info = _torrents_info(
            torrents=self._tm_client.api.torrents,
            order=self._tm_client.config_entry.options[CONF_ORDER],
            limit=self._tm_client.config_entry.options[CONF_LIMIT],
            statuses=self.SUBTYPE_MODES[self._sub_type],
        )
        return {
            STATE_ATTR_TORRENT_INFO: info,
        }

    def update(self):
        """Get the latest data from Transmission and updates the state."""
        torrents = _filter_torrents(
            self._tm_client.api.torrents, statuses=self.SUBTYPE_MODES[self._sub_type]
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
