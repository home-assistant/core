"""Summary data from Nextcoud."""
from __future__ import annotations

from datetime import datetime, timezone
from numbers import Number
from typing import Any, cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import BOOLEN_VALUES, DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity

ATTRS_B_IN_GB = {
    "device_class": SensorDeviceClass.DATA_SIZE,
    "native_unit_of_measurement": UnitOfInformation.BYTES,
    "suggested_display_precision": 2,
    "suggested_unit_of_measurement": UnitOfInformation.GIGABYTES,
}
ATTRS_B_IN_MB = {
    "device_class": SensorDeviceClass.DATA_SIZE,
    "native_unit_of_measurement": UnitOfInformation.BYTES,
    "suggested_display_precision": 1,
    "suggested_unit_of_measurement": UnitOfInformation.MEGABYTES,
}
ATTRS_KB_IN_GB = {
    "device_class": SensorDeviceClass.DATA_SIZE,
    "icon": "mdi:memory",
    "native_unit_of_measurement": UnitOfInformation.KILOBYTES,
    "suggested_display_precision": 2,
    "suggested_unit_of_measurement": UnitOfInformation.GIGABYTES,
}
ATTRS_S = {
    "device_class": SensorDeviceClass.DURATION,
    "native_unit_of_measurement": UnitOfTime.SECONDS,
}
ATTRS_TS = {
    "device_class": SensorDeviceClass.TIMESTAMP,
}
ATTRS_LOAD = {
    "native_unit_of_measurement": "",
    "suggested_display_precision": 3,
}
ATTRS_NUMERIC = {
    "native_unit_of_measurement": "",
}

SENSORS: dict[str, dict[str, Any]] = {
    "cache mem_size": ATTRS_B_IN_MB,
    "cache start_time": ATTRS_TS,
    "database size": ATTRS_B_IN_MB,
    "interned_strings_usage buffer_size": ATTRS_B_IN_MB,
    "interned_strings_usage free_memory": ATTRS_B_IN_MB,
    "interned_strings_usage used_memory": ATTRS_B_IN_MB,
    "jit buffer_free": ATTRS_B_IN_MB,
    "jit buffer_size": ATTRS_B_IN_MB,
    "opcache_statistics start_time": ATTRS_TS,
    "server php opcache memory_usage free_memory": ATTRS_B_IN_MB,
    "server php opcache memory_usage used_memory": ATTRS_B_IN_MB,
    "server php opcache memory_usage wasted_memory": ATTRS_B_IN_MB,
    "server php max_execution_time": ATTRS_S,
    "server php memory_limit": ATTRS_B_IN_MB,
    "server php upload_max_filesize": ATTRS_B_IN_MB,
    "sma avail_mem": ATTRS_B_IN_MB,
    "sma seg_size": ATTRS_B_IN_MB,
    "system cpuload": ATTRS_LOAD,
    "system freespace": ATTRS_B_IN_GB,
    "system mem_free": ATTRS_KB_IN_GB,
    "system mem_total": ATTRS_KB_IN_GB,
    "system swap_total": ATTRS_KB_IN_GB,
    "system swap_free": ATTRS_KB_IN_GB,
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
                attrs=SENSORS.get(
                    name,
                    ATTRS_NUMERIC
                    if isinstance(coordinator.data[name], Number)
                    else None,
                ),
            )
            for name in coordinator.data
            if not isinstance(coordinator.data[name], bool)
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
        if getattr(self, "_attr_device_class", None) == SensorDeviceClass.TIMESTAMP:
            return datetime.fromtimestamp(cast(int, val), tz=timezone.utc)
        return val
