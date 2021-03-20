"""Asuswrt status sensors."""
from __future__ import annotations

import logging
from numbers import Number

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_GIGABYTES,
    DATA_RATE_MEGABITS_PER_SECOND,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.typing import HomeAssistantType
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
from .router import KEY_COORDINATOR, KEY_SENSORS, SENSORS_TYPE_TEMP, AsusWrtRouter

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
        SENSOR_UNIT: PERCENTAGE,
        SENSOR_ICON: "mdi:cpu-32-bit",
    },
    SENSORS_LOAD_AVG[1]: {
        SENSOR_NAME: "Load Avg (5m)",
        SENSOR_UNIT: PERCENTAGE,
        SENSOR_ICON: "mdi:cpu-32-bit",
    },
    SENSORS_LOAD_AVG[2]: {
        SENSOR_NAME: "Load Avg (15m)",
        SENSOR_UNIT: PERCENTAGE,
        SENSOR_ICON: "mdi:cpu-32-bit",
    },
}

TEMPERATURE_SENSOR_TEMPLATE = {
    SENSOR_NAME: None,
    SENSOR_UNIT: TEMP_CELSIUS,
    SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""
    router: AsusWrtRouter = hass.data[DOMAIN][entry.entry_id][DATA_ASUSWRT]
    entities = []

    for sensor_type, sensor_data in router.sensors_coordinator.items():
        coordinator = sensor_data[KEY_COORDINATOR]
        sensors = sensor_data[KEY_SENSORS]
        for sensor_key in sensors:
            if sensor_type == SENSORS_TYPE_TEMP:
                sensor_def = {
                    **TEMPERATURE_SENSOR_TEMPLATE,
                    SENSOR_NAME: f"{sensor_key} Temperature",
                }
            else:
                sensor_def = CONNECTION_SENSORS.get(sensor_key)
            if sensor_def:
                entities.append(
                    AsusWrtSensor(coordinator, router, sensor_key, sensor_def)
                )

    async_add_entities(entities, True)


class AsusWrtSensor(CoordinatorEntity, SensorEntity):
    """Representation of a AsusWrt sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: AsusWrtRouter,
        sensor_type: str,
        sensor: dict[str, any],
    ) -> None:
        """Initialize a AsusWrt sensor."""
        super().__init__(coordinator)
        self._router = router
        self._sensor_type = sensor_type
        self._name = f"{DEFAULT_PREFIX} {sensor[SENSOR_NAME]}"
        self._unique_id = f"{DOMAIN} {self._name}"
        self._unit = sensor.get(SENSOR_UNIT)
        self._factor = sensor.get(SENSOR_FACTOR)
        self._icon = sensor.get(SENSOR_ICON)
        self._device_class = sensor.get(SENSOR_DEVICE_CLASS)
        self._default_enabled = sensor.get(SENSOR_DEFAULT_ENABLED, False)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._default_enabled

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
        return self._unit

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def device_class(self) -> str:
        """Return the device_class."""
        return self._device_class

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return the attributes."""
        return {"hostname": self._router.host}

    @property
    def device_info(self) -> dict[str, any]:
        """Return the device information."""
        return self._router.device_info
