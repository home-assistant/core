"""Asuswrt status sensors."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from numbers import Number
from typing import Any

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES, DATA_RATE_MEGABITS_PER_SECOND
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    DATA_ASUSWRT,
    DOMAIN,
    SENSORS_BYTES,
    SENSORS_CONNECTED_DEVICE,
    SENSORS_LOAD_AVG,
    SENSORS_RATES,
)
from .router import KEY_COORDINATOR, KEY_SENSORS, AsusWrtRouter


@dataclass
class AsusWrtSensorEntityDescription(SensorEntityDescription):
    """A class that describes AsusWrt sensor entities."""

    factor: int | None = None
    precision: int = 2


DEFAULT_PREFIX = "Asuswrt"
UNIT_DEVICES = "Devices"

CONNECTION_SENSORS: tuple[AsusWrtSensorEntityDescription, ...] = (
    AsusWrtSensorEntityDescription(
        key=SENSORS_CONNECTED_DEVICE[0],
        name="Devices Connected",
        icon="mdi:router-network",
        unit_of_measurement=UNIT_DEVICES,
        entity_registry_enabled_default=True,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_RATES[0],
        name="Download Speed",
        icon="mdi:download-network",
        unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        entity_registry_enabled_default=False,
        factor=125000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_RATES[1],
        name="Upload Speed",
        icon="mdi:upload-network",
        unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        entity_registry_enabled_default=False,
        factor=125000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_BYTES[0],
        name="Download",
        icon="mdi:download",
        unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
        factor=1000000000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_BYTES[1],
        name="Upload",
        icon="mdi:upload",
        unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
        factor=1000000000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[0],
        name="Load Avg (1m)",
        icon="mdi:cpu-32-bit",
        entity_registry_enabled_default=False,
        factor=1,
        precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[1],
        name="Load Avg (5m)",
        icon="mdi:cpu-32-bit",
        entity_registry_enabled_default=False,
        factor=1,
        precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[2],
        name="Load Avg (15m)",
        icon="mdi:cpu-32-bit",
        entity_registry_enabled_default=False,
        factor=1,
        precision=1,
    ),
)

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
        entities.extend(
            [
                AsusWrtSensor(coordinator, router, sensor_descr)
                for sensor_descr in CONNECTION_SENSORS
                if sensor_descr.key in sensors
            ]
        )

    async_add_entities(entities, True)


class AsusWrtSensor(CoordinatorEntity, SensorEntity):
    """Representation of a AsusWrt sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: AsusWrtRouter,
        description: AsusWrtSensorEntityDescription,
    ) -> None:
        """Initialize a AsusWrt sensor."""
        super().__init__(coordinator)
        self._router = router
        self.entity_description = description

        self._attr_name = f"{DEFAULT_PREFIX} {description.name}"
        self._attr_unique_id = f"{DOMAIN} {self.name}"
        self._attr_state_class = STATE_CLASS_MEASUREMENT

        if description.unit_of_measurement == DATA_GIGABYTES:
            self._attr_last_reset = dt_util.utc_from_timestamp(0)

    @property
    def state(self) -> str:
        """Return current state."""
        descr = self.entity_description
        state = self.coordinator.data.get(descr.key)
        if state is None:
            return None
        if descr.factor and isinstance(state, Number):
            return round(state / descr.factor, descr.precision)
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        return {"hostname": self._router.host}

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._router.device_info
