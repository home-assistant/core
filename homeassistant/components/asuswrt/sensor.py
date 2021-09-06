"""Asuswrt status sensors."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from numbers import Real

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES, DATA_RATE_MEGABITS_PER_SECOND
from homeassistant.core import HomeAssistant
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
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=UNIT_DEVICES,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_RATES[0],
        name="Download Speed",
        icon="mdi:download-network",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        entity_registry_enabled_default=False,
        factor=125000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_RATES[1],
        name="Upload Speed",
        icon="mdi:upload-network",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        entity_registry_enabled_default=False,
        factor=125000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_BYTES[0],
        name="Download",
        icon="mdi:download",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        native_unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
        factor=1000000000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_BYTES[1],
        name="Upload",
        icon="mdi:upload",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        native_unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
        factor=1000000000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[0],
        name="Load Avg (1m)",
        icon="mdi:cpu-32-bit",
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
        factor=1,
        precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[1],
        name="Load Avg (5m)",
        icon="mdi:cpu-32-bit",
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
        factor=1,
        precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[2],
        name="Load Avg (15m)",
        icon="mdi:cpu-32-bit",
        state_class=STATE_CLASS_MEASUREMENT,
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
        self.entity_description: AsusWrtSensorEntityDescription = description

        self._attr_name = f"{DEFAULT_PREFIX} {description.name}"
        self._attr_unique_id = f"{DOMAIN} {self.name}"
        self._attr_device_info = router.device_info
        self._attr_extra_state_attributes = {"hostname": router.host}

    @property
    def native_value(self) -> float | str | None:
        """Return current state."""
        descr = self.entity_description
        state = self.coordinator.data.get(descr.key)
        if state is not None and descr.factor and isinstance(state, Real):
            return round(state / descr.factor, descr.precision)
        return state
