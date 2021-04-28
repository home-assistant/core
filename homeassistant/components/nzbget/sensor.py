"""Monitor the NZBGet API."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    DATA_MEGABYTES,
    DATA_RATE_MEGABYTES_PER_SECOND,
    DEVICE_CLASS_TIMESTAMP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from . import NZBGetEntity
from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import NZBGetDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "article_cache": ["ArticleCacheMB", "Article Cache", DATA_MEGABYTES],
    "average_download_rate": [
        "AverageDownloadRate",
        "Average Speed",
        DATA_RATE_MEGABYTES_PER_SECOND,
    ],
    "download_paused": ["DownloadPaused", "Download Paused", None],
    "download_rate": ["DownloadRate", "Speed", DATA_RATE_MEGABYTES_PER_SECOND],
    "download_size": ["DownloadedSizeMB", "Size", DATA_MEGABYTES],
    "free_disk_space": ["FreeDiskSpaceMB", "Disk Free", DATA_MEGABYTES],
    "post_job_count": ["PostJobCount", "Post Processing Jobs", "Jobs"],
    "post_paused": ["PostPaused", "Post Processing Paused", None],
    "remaining_size": ["RemainingSizeMB", "Queue Size", DATA_MEGABYTES],
    "uptime": ["UpTimeSec", "Uptime", None],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NZBGet sensor based on a config entry."""
    coordinator: NZBGetDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    sensors = []

    for sensor_config in SENSOR_TYPES.values():
        sensors.append(
            NZBGetSensor(
                coordinator,
                entry.entry_id,
                entry.data[CONF_NAME],
                sensor_config[0],
                sensor_config[1],
                sensor_config[2],
            )
        )

    async_add_entities(sensors)


class NZBGetSensor(NZBGetEntity, SensorEntity):
    """Representation of a NZBGet sensor."""

    def __init__(
        self,
        coordinator: NZBGetDataUpdateCoordinator,
        entry_id: str,
        entry_name: str,
        sensor_type: str,
        sensor_name: str,
        unit_of_measurement: str | None = None,
    ):
        """Initialize a new NZBGet sensor."""
        self._sensor_type = sensor_type
        self._unique_id = f"{entry_id}_{sensor_type}"
        self._unit_of_measurement = unit_of_measurement

        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            name=f"{entry_name} {sensor_name}",
        )

    @property
    def device_class(self):
        """Return the device class."""
        if "UpTimeSec" in self._sensor_type:
            return DEVICE_CLASS_TIMESTAMP

        return None

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit that the state of sensor is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        value = self.coordinator.data["status"].get(self._sensor_type)

        if value is None:
            _LOGGER.warning("Unable to locate value for %s", self._sensor_type)
            return None

        if "DownloadRate" in self._sensor_type and value > 0:
            # Convert download rate from Bytes/s to MBytes/s
            return round(value / 2 ** 20, 2)

        if "UpTimeSec" in self._sensor_type and value > 0:
            uptime = utcnow() - timedelta(seconds=value)
            return uptime.replace(microsecond=0).isoformat()

        return value
