"""Support for monitoring the qBittorrent API."""
from __future__ import annotations

import logging

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    DATA_RATE_KILOBYTES_PER_SECOND,
    STATE_IDLE,
)
import homeassistant.helpers.config_validation as cv

from .client import get_main_data_client
from .const import (
    DATA_KEY_CLIENT,
    DATA_KEY_NAME,
    DOMAIN,
    SENSOR_TYPE_CURRENT_STATUS,
    SENSOR_TYPE_DOWNLOAD_SPEED,
    SENSOR_TYPE_UPLOAD_SPEED,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TYPE_CURRENT_STATUS, name="Status", native_unit_of_measurement=None
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_SPEED,
        name="Down Speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_UPLOAD_SPEED,
        name="Up Speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DOMAIN): cv.string,
    }
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the qBittorrent sensor."""

    qbit_data = hass.data[DOMAIN][entry.data[CONF_URL]]
    name = qbit_data[DATA_KEY_NAME]
    sensors = [
        QBittorrentSensor(
            qbit_data[DATA_KEY_CLIENT],
            name,
            LoginRequired,
            entry.entry_id,
            sensordiscription,
        )
        for sensordiscription in SENSOR_TYPES
    ]
    async_add_entities(sensors, True)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class QBittorrentSensor(SensorEntity):
    """Representation of an qBittorrent sensor."""

    def __init__(
        self,
        qbittorrent_client,
        client_name,
        exception,
        server_unique_id,
        description: SensorEntityDescription,
    ):
        """Initialize the qBittorrent sensor."""
        self.entity_description = description
        self.client = qbittorrent_client
        self._exception = exception
        self._server_unique_id = server_unique_id
        self._attr_name = f"{client_name} {description.name}"
        self._attr_available = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._attr_name}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._attr_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._attr_native_value

    @property
    def available(self):
        """Return true if device is available."""
        return self._attr_available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.entity_description.native_unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:cloud-download"

    @property
    def device_info(self):
        """Return the device information of the entity."""
        return {
            "identifiers": {(DOMAIN, self._server_unique_id)},
            "name": DOMAIN,
            "model": DOMAIN,
            "manufacturer": DOMAIN,
        }

    async def async_update(self):
        """Get the latest data from qBittorrent and updates the state."""
        try:
            data = await self.hass.async_add_executor_job(
                get_main_data_client, self.client
            )
            if not self._attr_available:
                _LOGGER.info("Reconnected with QBittorent server")

            self._attr_available = True
        except RequestException:
            if self._attr_available:
                _LOGGER.error("Connection lost")
                self._attr_available = False
        except self._exception:
            _LOGGER.error("Invalid authentication")
            self._attr_available = False
            return

        if data is None:
            return

        download = data["server_state"]["dl_info_speed"]
        upload = data["server_state"]["up_info_speed"]

        sensor_type = self.entity_description.key
        if sensor_type == SENSOR_TYPE_CURRENT_STATUS:
            if upload > 0 and download > 0:
                self._attr_native_value = "up_down"
            elif upload > 0 and download == 0:
                self._attr_native_value = "seeding"
            elif upload == 0 and download > 0:
                self._attr_native_value = "downloading"
            else:
                self._attr_native_value = STATE_IDLE

        elif sensor_type == SENSOR_TYPE_DOWNLOAD_SPEED:
            self._attr_native_value = format_speed(download)
        elif sensor_type == SENSOR_TYPE_UPLOAD_SPEED:
            self._attr_native_value = format_speed(upload)
