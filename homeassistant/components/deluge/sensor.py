"""Support for monitoring the Deluge BitTorrent client API."""
from __future__ import annotations

import logging

from deluge_client import DelugeRPCClient, FailedToReconnectException
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    DATA_RATE_KILOBYTES_PER_SECOND,
    STATE_IDLE,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_THROTTLED_REFRESH = None

DEFAULT_NAME = "Deluge"
DEFAULT_PORT = 58846
DHT_UPLOAD = 1000
DHT_DOWNLOAD = 1000
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="current_status",
        name="Status",
    ),
    SensorEntityDescription(
        key="download_speed",
        name="Down Speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
    ),
    SensorEntityDescription(
        key="upload_speed",
        name="Up Speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Deluge sensors."""

    name = config[CONF_NAME]
    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    port = config[CONF_PORT]

    deluge_api = DelugeRPCClient(host, port, username, password)
    try:
        deluge_api.connect()
    except ConnectionRefusedError as err:
        _LOGGER.error("Connection to Deluge Daemon failed")
        raise PlatformNotReady from err
    monitored_variables = config[CONF_MONITORED_VARIABLES]
    entities = [
        DelugeSensor(deluge_api, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_variables
    ]

    add_entities(entities)


class DelugeSensor(SensorEntity):
    """Representation of a Deluge sensor."""

    def __init__(
        self, deluge_client, client_name, description: SensorEntityDescription
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self.client = deluge_client
        self.data = None

        self._attr_available = False
        self._attr_name = f"{client_name} {description.name}"

    def update(self):
        """Get the latest data from Deluge and updates the state."""

        try:
            self.data = self.client.call(
                "core.get_session_status",
                [
                    "upload_rate",
                    "download_rate",
                    "dht_upload_rate",
                    "dht_download_rate",
                ],
            )
            self._attr_available = True
        except FailedToReconnectException:
            _LOGGER.error("Connection to Deluge Daemon Lost")
            self._attr_available = False
            return

        upload = self.data[b"upload_rate"] - self.data[b"dht_upload_rate"]
        download = self.data[b"download_rate"] - self.data[b"dht_download_rate"]

        sensor_type = self.entity_description.key
        if sensor_type == "current_status":
            if self.data:
                if upload > 0 and download > 0:
                    self._attr_native_value = "Up/Down"
                elif upload > 0 and download == 0:
                    self._attr_native_value = "Seeding"
                elif upload == 0 and download > 0:
                    self._attr_native_value = "Downloading"
                else:
                    self._attr_native_value = STATE_IDLE
            else:
                self._attr_native_value = None

        if self.data:
            if sensor_type == "download_speed":
                kb_spd = float(download)
                kb_spd = kb_spd / 1024
                self._attr_native_value = round(kb_spd, 2 if kb_spd < 0.1 else 1)
            elif sensor_type == "upload_speed":
                kb_spd = float(upload)
                kb_spd = kb_spd / 1024
                self._attr_native_value = round(kb_spd, 2 if kb_spd < 0.1 else 1)
