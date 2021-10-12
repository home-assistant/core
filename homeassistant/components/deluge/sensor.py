"""Support for monitoring the Deluge BitTorrent client API."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME, DATA_RATE_MEGABYTES_PER_SECOND, STATE_IDLE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DelugeClient
from .const import (
    DOMAIN,
    STATE_ATTR_FREE_SPACE,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Deluge sensors."""

    deluge_client = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]

    entities = [
        DelugeSpeedSensor(deluge_client, name, "Down Speed", "download"),
        DelugeSpeedSensor(deluge_client, name, "Up Speed", "upload"),
        DelugeStatusSensor(deluge_client, name, "Status"),
    ]

    async_add_entities(entities, True)


class DelugeSensor(SensorEntity):
    """A base class for all Deluge sensors."""

    @staticmethod
    def _get_session_speeds(session):
        return (
            session[b"download_rate"] - session[b"dht_download_rate"],
            session[b"upload_rate"] - session[b"dht_upload_rate"],
        )

    def __init__(self, deluge_client, client_name, sensor_name, sub_type=None):
        """Initialize the sensor."""
        self._deluge_client: DelugeClient = deluge_client
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
        return f"{self._deluge_client.state.host}-{self.name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._deluge_client.state.available

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._deluge_client.state.signal_update, update
            )
        )


class DelugeSpeedSensor(DelugeSensor):
    """Representation of a Deluge speed sensor."""

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return DATA_RATE_MEGABYTES_PER_SECOND

    def update(self):
        """Get the latest data from Deluge and updates the state."""
        session = self._deluge_client.state.session
        if session:
            download, upload = self._get_session_speeds(session)
            value = float(download if self._sub_type == "download" else upload)
            value = value / 1024 / 1024  # Convert from bytes to MiB
            self._state = round(value, 2 if value < 0.1 else 1)
        else:
            self._state = None


class DelugeStatusSensor(DelugeSensor):
    """Representation of a Deluge status sensor."""

    @property
    def extra_state_attributes(self):
        """Return the state attributes, if any."""
        session = self._deluge_client.state.session
        value = session[b"free_space"] / 1024 / 1024 / 1024  # Convert from bytes to GiB
        return {STATE_ATTR_FREE_SPACE: round(value, 2 if value < 0.1 else 1)}

    def update(self):
        """Get the latest data from Deluge and updates the state."""
        session = self._deluge_client.state.session
        if session:
            download, upload = self._get_session_speeds(session)
            if download > 0 and upload > 0:
                self._state = "Up/Down"
            elif download == 0 and upload > 0:
                self._state = "Seeding"
            elif download > 0 and upload == 0:
                self._state = "Downloading"
            else:
                self._state = STATE_IDLE
        else:
            self._state = None
