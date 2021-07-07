"""Asuswrt status sensors."""
from __future__ import annotations

import logging
from numbers import Number
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES, DATA_RATE_MEGABITS_PER_SECOND
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DATA_ASUSWRT,
    DOMAIN,
    SENSORS_BYTES,
    SENSORS_CONNECTED_DEVICE,
    SENSORS_LOAD_AVG,
    SENSORS_RATES,
)
from .router import KEY_COORDINATOR, KEY_SENSORS, AsusWrtRouter

DEFAULT_PREFIX = "Asuswrt"

SENSOR_DEVICE_CLASS = "device_class"
SENSOR_ICON = "icon"
SENSOR_NAME = "name"
SENSOR_UNIT = "unit"
SENSOR_FACTOR = "factor"
SENSOR_DEFAULT_ENABLED = "default_enabled"

UNIT_DEVICES = "Devices"

CONNECTION_SENSORS = {
    SENSORS_CONNECTED_DEVICE[0]: {
        SENSOR_NAME: "Devices Connected",
        SENSOR_UNIT: UNIT_DEVICES,
        SENSOR_FACTOR: 0,
        SENSOR_ICON: "mdi:router-network",
        SENSOR_DEFAULT_ENABLED: True,
    },
    SENSORS_RATES[0]: {
        SENSOR_NAME: "Download Speed",
        SENSOR_UNIT: DATA_RATE_MEGABITS_PER_SECOND,
        SENSOR_FACTOR: 125000,
        SENSOR_ICON: "mdi:download-network",
    },
    SENSORS_RATES[1]: {
        SENSOR_NAME: "Upload Speed",
        SENSOR_UNIT: DATA_RATE_MEGABITS_PER_SECOND,
        SENSOR_FACTOR: 125000,
        SENSOR_ICON: "mdi:upload-network",
    },
    SENSORS_BYTES[0]: {
        SENSOR_NAME: "Download",
        SENSOR_UNIT: DATA_GIGABYTES,
        SENSOR_FACTOR: 1000000000,
        SENSOR_ICON: "mdi:download",
    },
    SENSORS_BYTES[1]: {
        SENSOR_NAME: "Upload",
        SENSOR_UNIT: DATA_GIGABYTES,
        SENSOR_FACTOR: 1000000000,
        SENSOR_ICON: "mdi:upload",
    },
    SENSORS_LOAD_AVG[0]: {
        SENSOR_NAME: "Load Avg (1m)",
        SENSOR_ICON: "mdi:cpu-32-bit",
    },
    SENSORS_LOAD_AVG[1]: {
        SENSOR_NAME: "Load Avg (5m)",
        SENSOR_ICON: "mdi:cpu-32-bit",
    },
    SENSORS_LOAD_AVG[2]: {
        SENSOR_NAME: "Load Avg (15m)",
        SENSOR_ICON: "mdi:cpu-32-bit",
    },
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""
    router: AsusWrtRouter = hass.data[DOMAIN][entry.entry_id][DATA_ASUSWRT]
    entities = []

    for sensor_data in router.sensors_coordinator.values():
        coordinator = sensor_data[KEY_COORDINATOR]
        sensors = sensor_data[KEY_SENSORS]
        for sensor_key in sensors:
            if sensor_key in CONNECTION_SENSORS:
                entities.append(
                    AsusWrtSensor(
                        coordinator, router, sensor_key, CONNECTION_SENSORS[sensor_key]
                    )
                )

    async_add_entities(entities, True)


class AsusWrtSensor(CoordinatorEntity, SensorEntity):
    """Representation of a AsusWrt sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: AsusWrtRouter,
        sensor_type: str,
        sensor_def: dict[str, Any],
    ) -> None:
        """Initialize a AsusWrt sensor."""
        super().__init__(coordinator)
        self._router = router
        self._sensor_type = sensor_type
        self._sensor_def = sensor_def
        self._name = f"{DEFAULT_PREFIX} {sensor_def[SENSOR_NAME]}"
        self._unique_id = f"{DOMAIN} {self._name}"
        self._factor = sensor_def.get(SENSOR_FACTOR)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._sensor_def.get(SENSOR_DEFAULT_ENABLED, False)

    @property
    def state(self) -> str:
        """Return current state."""
        state = self.coordinator.data.get(self._sensor_type)
        if state is None:
            return None
        if self._factor and isinstance(state, Number):
            return round(state / self._factor, 2)
        return state

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit."""
        return self._sensor_def.get(SENSOR_UNIT)

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._sensor_def.get(SENSOR_ICON)

    @property
    def device_class(self) -> str:
        """Return the device_class."""
        return self._sensor_def.get(SENSOR_DEVICE_CLASS)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        return {"hostname": self._router.host}

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._router.device_info
