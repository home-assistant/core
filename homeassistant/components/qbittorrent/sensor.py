"""Support for monitoring the qBittorrent API."""
from __future__ import annotations

import logging

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_IDLE,
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    SENSOR_TYPE_CURRENT_STATUS,
    SENSOR_TYPE_DOWNLOAD_SPEED,
    SENSOR_TYPE_UPLOAD_SPEED,
)
from .helpers import setup_client

from .const import DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key=SENSOR_TYPE_CURRENT_STATUS, name="Status"),
    SensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_SPEED,
        name="Down Speed",
        icon="mdi:cloud-download",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_UPLOAD_SPEED,
        name="Up Speed",
        icon="mdi:cloud-upload",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entites: AddEntitiesCallback,
) -> None:
    """Set up qBittorrent sensor entries."""
    client = await hass.async_add_executor_job(
        setup_client,
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_VERIFY_SSL],
    )

    name = entry.data[CONF_NAME]

    entities = [
        QBittorrentSensor(description, client, name, LoginRequired)
        for description in SENSOR_TYPES
    ]

    async_add_entites(entities, True)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class QBittorrentSensor(SensorEntity):
    """Representation of an qBittorrent sensor."""

    def __init__(
        self,
        description: SensorEntityDescription,
        qbittorrent_client,
        client_name,
        exception,
    ) -> None:
        """Initialize the qBittorrent sensor."""
        self.entity_description = description
        self.client = qbittorrent_client
        self._exception = exception

        self._attr_unique_id = f"{client_name}-{description.key}".lower()
        self._attr_name = f"{client_name} {description.name}"
        self._attr_icon = description.icon
        self._attr_available = False

    def update(self) -> None:
        """Get the latest data from qBittorrent and updates the state."""
        try:
            data = self.client.sync_main_data()
            self._attr_available = True
        except RequestException:
            _LOGGER.error("Connection lost")
            self._attr_available = False
            return
        except self._exception:
            _LOGGER.error("Invalid authentication")
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
