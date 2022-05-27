"""Monitor the NZBGet API."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    DATA_MEGABYTES,
    DATA_RATE_MEGABYTES_PER_SECOND,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from . import NZBGetEntity
from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import NZBGetDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ArticleCacheMB",
        name="Article Cache",
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
    SensorEntityDescription(
        key="AverageDownloadRate",
        name="Average Speed",
        native_unit_of_measurement=DATA_RATE_MEGABYTES_PER_SECOND,
    ),
    SensorEntityDescription(
        key="DownloadPaused",
        name="Download Paused",
    ),
    SensorEntityDescription(
        key="DownloadRate",
        name="Speed",
        native_unit_of_measurement=DATA_RATE_MEGABYTES_PER_SECOND,
    ),
    SensorEntityDescription(
        key="DownloadedSizeMB",
        name="Size",
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
    SensorEntityDescription(
        key="FreeDiskSpaceMB",
        name="Disk Free",
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
    SensorEntityDescription(
        key="PostJobCount",
        name="Post Processing Jobs",
        native_unit_of_measurement="Jobs",
    ),
    SensorEntityDescription(
        key="PostPaused",
        name="Post Processing Paused",
    ),
    SensorEntityDescription(
        key="RemainingSizeMB",
        name="Queue Size",
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
    SensorEntityDescription(
        key="UpTimeSec",
        name="Uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NZBGet sensor based on a config entry."""
    coordinator: NZBGetDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    entities = [
        NZBGetSensor(coordinator, entry.entry_id, entry.data[CONF_NAME], description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class NZBGetSensor(NZBGetEntity, SensorEntity):
    """Representation of a NZBGet sensor."""

    def __init__(
        self,
        coordinator: NZBGetDataUpdateCoordinator,
        entry_id: str,
        entry_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a new NZBGet sensor."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            name=f"{entry_name} {description.name}",
        )

        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._native_value: datetime | None = None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        sensor_type = self.entity_description.key
        value = self.coordinator.data["status"].get(sensor_type)

        if value is None:
            _LOGGER.warning("Unable to locate value for %s", sensor_type)
            self._native_value = None
        elif "DownloadRate" in sensor_type and value > 0:
            # Convert download rate from Bytes/s to MBytes/s
            self._native_value = round(value / 2**20, 2)
        elif "UpTimeSec" in sensor_type and value > 0:
            uptime = utcnow().replace(microsecond=0) - timedelta(seconds=value)
            if not isinstance(self._attr_native_value, datetime) or abs(
                uptime - self._attr_native_value
            ) > timedelta(seconds=5):
                self._native_value = uptime
        else:
            self._native_value = value

        return self._native_value
