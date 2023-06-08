"""Summary data from Nextcoud."""
from __future__ import annotations

from datetime import datetime, timezone
from numbers import Number
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import BOOLEN_VALUES, DOMAIN, IGNORE_SENSORS
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity

DESC_B_IN_GB = SensorEntityDescription(
    key="bytes in gigabyte",
    device_class=SensorDeviceClass.DATA_SIZE,
    native_unit_of_measurement=UnitOfInformation.BYTES,
    suggested_display_precision=2,
    suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
)
DESC_B_IN_MB = SensorEntityDescription(
    key="bytes in megabyte",
    device_class=SensorDeviceClass.DATA_SIZE,
    native_unit_of_measurement=UnitOfInformation.BYTES,
    suggested_display_precision=1,
    suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
)
DESC_KB_IN_GB = SensorEntityDescription(
    key="kilobytes in gigabyte",
    device_class=SensorDeviceClass.DATA_SIZE,
    icon="mdi:memory",
    native_unit_of_measurement=UnitOfInformation.KILOBYTES,
    suggested_display_precision=2,
    suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
)
DESC_S = SensorEntityDescription(
    key="seconds",
    device_class=SensorDeviceClass.DURATION,
    native_unit_of_measurement=UnitOfTime.SECONDS,
)
DESC_TS = SensorEntityDescription(
    key="timestamp",
    device_class=SensorDeviceClass.TIMESTAMP,
)
DESC_LOAD = SensorEntityDescription(
    key="cpuload",
    native_unit_of_measurement="",
    suggested_display_precision=3,
)
DESC_NUMERIC = SensorEntityDescription(
    key="numeric",
    native_unit_of_measurement="",
)

SENSORS: dict[str, SensorEntityDescription] = {
    "cache mem_size": DESC_B_IN_MB,
    "cache start_time": DESC_TS,
    "database size": DESC_B_IN_MB,
    "interned_strings_usage buffer_size": DESC_B_IN_MB,
    "interned_strings_usage free_memory": DESC_B_IN_MB,
    "interned_strings_usage used_memory": DESC_B_IN_MB,
    "jit buffer_free": DESC_B_IN_MB,
    "jit buffer_size": DESC_B_IN_MB,
    "opcache_statistics start_time": DESC_TS,
    "server php opcache memory_usage free_memory": DESC_B_IN_MB,
    "server php opcache memory_usage used_memory": DESC_B_IN_MB,
    "server php opcache memory_usage wasted_memory": DESC_B_IN_MB,
    "server php max_execution_time": DESC_S,
    "server php memory_limit": DESC_B_IN_MB,
    "server php upload_max_filesize": DESC_B_IN_MB,
    "sma avail_mem": DESC_B_IN_MB,
    "sma seg_size": DESC_B_IN_MB,
    "system cpuload": DESC_LOAD,
    "system freespace": DESC_B_IN_GB,
    "system mem_free": DESC_KB_IN_GB,
    "system mem_total": DESC_KB_IN_GB,
    "system swap_total": DESC_KB_IN_GB,
    "system swap_free": DESC_KB_IN_GB,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud sensors."""
    coordinator: NextcloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextcloudSensor(
                coordinator,
                name,
                entry,
                SENSORS.get(
                    name,
                    DESC_NUMERIC
                    if isinstance(coordinator.data[name], Number)
                    else None,
                ),
            )
            for name in coordinator.data
            if name not in IGNORE_SENSORS
            and not isinstance(coordinator.data[name], bool)
            and coordinator.data[name] not in BOOLEN_VALUES
        ]
    )


class NextcloudSensor(NextcloudEntity, SensorEntity):
    """Represents a Nextcloud sensor."""

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state for this sensor."""
        val = self.coordinator.data.get(self.item)
        if self.item == "system cpuload":
            return val[0] if isinstance(val, list) else None
        if (
            getattr(self.entity_description, "device_class", None)
            == SensorDeviceClass.TIMESTAMP
        ):
            return datetime.fromtimestamp(cast(int, val), tz=timezone.utc)
        return val
