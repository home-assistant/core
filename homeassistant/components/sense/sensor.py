"""Support for monitoring a Sense energy sensor."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import partial

from sense_energy import ASyncSenseable, Scale
from sense_energy.sense_api import SenseDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SenseConfigEntry
from .const import (
    ACTIVE_TYPE,
    CONSUMPTION_ID,
    FROM_GRID_ID,
    NET_PRODUCTION_ID,
    PRODUCTION_ID,
    PRODUCTION_PCT_ID,
    SOLAR_POWERED_ID,
    TO_GRID_ID,
)
from .coordinator import SenseCoordinator
from .entity import SenseDeviceEntity, SenseEntity

# Sensor types/ranges
TRENDS_SENSOR_TYPES = {
    Scale.DAY: "daily",
    Scale.WEEK: "weekly",
    Scale.MONTH: "monthly",
    Scale.YEAR: "yearly",
    Scale.CYCLE: "bill",
}

# Trend production/consumption variants
TREND_SENSOR_VARIANTS = [
    PRODUCTION_ID,
    CONSUMPTION_ID,
    NET_PRODUCTION_ID,
    FROM_GRID_ID,
    TO_GRID_ID,
]
TREND_SENSOR_PCT_VARIANTS = [PRODUCTION_PCT_ID, SOLAR_POWERED_ID]


class CoordinatorType(Enum):
    """Types of Coordinators."""

    TREND = "trend"
    REALTIME = "realtime"


@dataclass(frozen=True, kw_only=True)
class SenseSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Sensor entity."""

    value_fn: Callable[[ASyncSenseable], float]
    last_reset_fn: Callable[[ASyncSenseable], datetime | None] | None = None
    coordinator_type: CoordinatorType


@dataclass(frozen=True, kw_only=True)
class SenseDeviceSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Sensor entity."""

    value_fn: Callable[[SenseDevice], float]
    coordinator_type: CoordinatorType


ENTITY_DESCRIPTIONS = [
    SenseSensorEntityDescription(
        key=f"{ACTIVE_TYPE}-{PRODUCTION_ID}",
        translation_key=f"{ACTIVE_TYPE}_{PRODUCTION_ID}",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.active_solar_power,
        coordinator_type=CoordinatorType.REALTIME,
    ),
    SenseSensorEntityDescription(
        key=f"{ACTIVE_TYPE}-{CONSUMPTION_ID}",
        translation_key=f"{ACTIVE_TYPE}_{CONSUMPTION_ID}",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.active_power,
        coordinator_type=CoordinatorType.REALTIME,
    ),
]

ENTITY_DESCRIPTIONS.extend(
    SenseSensorEntityDescription(
        key=f"L{i+1}",
        translation_key=f"voltage_{i}",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=partial(lambda gateway, ind: gateway.active_voltage[ind], ind=i),
        coordinator_type=CoordinatorType.REALTIME,
    )
    for i in range(2)
)

ENTITY_DESCRIPTIONS.extend(
    SenseSensorEntityDescription(
        key=f"{TRENDS_SENSOR_TYPES[scale]}-{variant_id}",
        translation_key=f"{TRENDS_SENSOR_TYPES[scale]}_{variant_id}",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        value_fn=partial(
            lambda gateway, s, vid: gateway.get_stat(s, vid), s=scale, vid=variant_id
        ),
        last_reset_fn=partial(lambda gateway, s: gateway.trend_start(s), s=scale),
        coordinator_type=CoordinatorType.TREND,
    )
    for scale in Scale
    for variant_id in TREND_SENSOR_VARIANTS
)
ENTITY_DESCRIPTIONS.extend(
    SenseSensorEntityDescription(
        key=f"{TRENDS_SENSOR_TYPES[scale]}-{variant_id}",
        translation_key=f"{TRENDS_SENSOR_TYPES[scale]}_{variant_id}",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=partial(
            lambda gateway, s, vid: gateway.get_stat(s, vid), s=scale, vid=variant_id
        ),
        coordinator_type=CoordinatorType.TREND,
    )
    for scale in Scale
    for variant_id in TREND_SENSOR_PCT_VARIANTS
)

DEVICE_ENTITY_DESCRIPTIONS = [
    SenseDeviceSensorEntityDescription(
        key=CONSUMPTION_ID,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.power_w,
        coordinator_type=CoordinatorType.REALTIME,
    )
]
DEVICE_ENTITY_DESCRIPTIONS.extend(
    SenseDeviceSensorEntityDescription(
        key=f"{TRENDS_SENSOR_TYPES[scale]}-energy",
        translation_key=f"{TRENDS_SENSOR_TYPES[scale]}_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=partial(lambda device, s: device.energy_kwh[s], s=scale),
        coordinator_type=CoordinatorType.TREND,
    )
    for scale in Scale
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SenseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sense sensor."""
    data = config_entry.runtime_data.data
    coordinators = {
        CoordinatorType.REALTIME: config_entry.runtime_data.rt,
        CoordinatorType.TREND: config_entry.runtime_data.trends,
    }

    entities: list[SensorEntity] = [
        SenseSensor(data, coordinators[ed.coordinator_type], ed)
        for ed in ENTITY_DESCRIPTIONS
    ]
    entities.extend(
        SenseDeviceSensor(
            device, data.sense_monitor_id, coordinators[ed.coordinator_type], ed
        )
        for ed in DEVICE_ENTITY_DESCRIPTIONS
        for device in config_entry.runtime_data.data.devices
    )
    async_add_entities(entities)


class SenseSensor(SenseEntity, SensorEntity):
    """Representation of a Sense energy sensor."""

    entity_description: SenseSensorEntityDescription

    def __init__(
        self,
        gateway: ASyncSenseable,
        coordinator: SenseCoordinator,
        entity_description: SenseSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(gateway, coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def native_value(self) -> float:
        """State of the sensor."""
        return self.entity_description.value_fn(self._gateway)

    @property
    def last_reset(self) -> datetime | None:
        """Last time sensor was reset."""
        if self.entity_description.last_reset_fn is not None:
            return self.entity_description.last_reset_fn(self._gateway)
        return None


class SenseDeviceSensor(SenseDeviceEntity, SensorEntity):
    """Representation of a Sense energy sensor."""

    entity_description: SenseDeviceSensorEntityDescription

    def __init__(
        self,
        device: SenseDevice,
        sense_monitor_id: str,
        coordinator: SenseCoordinator,
        entity_description: SenseDeviceSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            device,
            coordinator,
            sense_monitor_id,
            f"{device.id}-{entity_description.key}",
        )
        self.entity_description = entity_description

    @property
    def native_value(self) -> float:
        """State of the sensor."""
        return self.entity_description.value_fn(self._device)
