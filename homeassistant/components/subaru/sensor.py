"""Support for Subaru sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any, override

import subarulink.const as sc

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfPressure,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_conversion import DistanceConverter, VolumeConverter
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    API_GEN_2,
    API_GEN_3,
    API_GEN_4,
    KEY_RECOMMENDED_TIRE_PRESSURE_FRONT,
    KEY_RECOMMENDED_TIRE_PRESSURE_REAR,
    VEHICLE_API_GEN,
    VEHICLE_HAS_EV,
    VEHICLE_HEALTH,
    VEHICLE_STATUS,
)
from .coordinator import SubaruConfigEntry, SubaruDataUpdateCoordinator
from .entity import SubaruCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


# Fuel consumption units
FUEL_CONSUMPTION_LITERS_PER_HUNDRED_KILOMETERS = "L/100km"
FUEL_CONSUMPTION_MILES_PER_GALLON = "mi/gal"

L_PER_GAL = VolumeConverter.convert(1, UnitOfVolume.GALLONS, UnitOfVolume.LITERS)
KM_PER_MI = DistanceConverter.convert(1, UnitOfLength.MILES, UnitOfLength.KILOMETERS)

# Readable aliases for subarulink field-key constants.
API_KEY_VEHICLE_STATE_TYPE = sc.VEHICLE_STATE
API_KEY_RECOMMENDED_TIRE_PRESSURE = sc.HEALTH_RECOMMENDED_TIRE_PRESSURE
API_KEY_FRONT_TIRES = sc.HEALTH_RECOMMENDED_TIRE_PRESSURE_FRONT
API_KEY_REAR_TIRES = sc.HEALTH_RECOMMENDED_TIRE_PRESSURE_REAR


@dataclass(frozen=True, kw_only=True)
class SubaruSensorEntityDescription(SensorEntityDescription):
    """Describes a Subaru sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType] | None = None


def _recommended_tire_pressure(axle: str) -> Callable[[dict[str, Any]], StateType]:
    """Return a getter for recommended FRONT or REAR axle tire pressure from vehicle_health."""

    def getter(data: dict[str, Any]) -> StateType:
        health = data.get(VEHICLE_HEALTH) or {}
        recommended = health.get(API_KEY_RECOMMENDED_TIRE_PRESSURE) or {}
        return recommended.get(axle)

    return getter


# Snake-case ENUM options for vehicle_state. Authoritative values confirmed by
# the integration codeowner against the Subaru Android app source (see PR
# #174054 discussion_r3488335137 and subarulink PR G-Two/subarulink#121).
# IGN-ACC, IGN-ON, and ENGINE_ON_REMOTE_START are not yet exported as
# `sc.*` constants in the released subarulink; the literal strings will be
# replaced once the next subarulink pin lands.
VEHICLE_STATE_OPTIONS = {
    sc.IGNITION_OFF: "ignition_off",
    "IGN-ACC": "ignition_acc",
    "IGN-ON": "ignition_on",
    "ENGINE_ON_REMOTE_START": "engine_on_remote_start",
}


def _vehicle_state_enum(data: dict[str, Any]) -> StateType:
    """Map the raw VEHICLE_STATE_TYPE to a snake_case ENUM option (unmapped → None → `unknown`)."""
    raw = (data.get(VEHICLE_STATUS) or {}).get(API_KEY_VEHICLE_STATE_TYPE)
    if raw is None:
        return None
    return VEHICLE_STATE_OPTIONS.get(raw)


# Sensor available for Gen1 or Gen2 vehicles
SAFETY_SENSORS = [
    SubaruSensorEntityDescription(
        key=sc.ODOMETER,
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILES,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]

# Sensors available to subscribers with Gen2/Gen3 vehicles
API_GEN_2_SENSORS = [
    SubaruSensorEntityDescription(
        key=sc.AVG_FUEL_CONSUMPTION,
        translation_key="average_fuel_consumption",
        native_unit_of_measurement=FUEL_CONSUMPTION_MILES_PER_GALLON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SubaruSensorEntityDescription(
        key=sc.DIST_TO_EMPTY,
        translation_key="range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SubaruSensorEntityDescription(
        key=sc.TIRE_PRESSURE_FL,
        translation_key="tire_pressure_front_left",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SubaruSensorEntityDescription(
        key=sc.TIRE_PRESSURE_FR,
        translation_key="tire_pressure_front_right",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SubaruSensorEntityDescription(
        key=sc.TIRE_PRESSURE_RL,
        translation_key="tire_pressure_rear_left",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SubaruSensorEntityDescription(
        key=sc.TIRE_PRESSURE_RR,
        translation_key="tire_pressure_rear_right",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SubaruSensorEntityDescription(
        key=API_KEY_VEHICLE_STATE_TYPE,
        translation_key="vehicle_state",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(VEHICLE_STATE_OPTIONS.values()),
        value_fn=_vehicle_state_enum,
    ),
    # Static manufacturer reference value, not a live measurement; no state_class.
    SubaruSensorEntityDescription(
        key=KEY_RECOMMENDED_TIRE_PRESSURE_FRONT,
        translation_key=KEY_RECOMMENDED_TIRE_PRESSURE_FRONT,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_recommended_tire_pressure(API_KEY_FRONT_TIRES),
    ),
    SubaruSensorEntityDescription(
        key=KEY_RECOMMENDED_TIRE_PRESSURE_REAR,
        translation_key=KEY_RECOMMENDED_TIRE_PRESSURE_REAR,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_recommended_tire_pressure(API_KEY_REAR_TIRES),
    ),
]

# Sensors available for Gen3 vehicles
API_GEN_3_SENSORS = [
    SubaruSensorEntityDescription(
        key=sc.REMAINING_FUEL_PERCENT,
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

# Sensors available to subscribers with PHEV vehicles
EV_SENSORS = [
    SubaruSensorEntityDescription(
        key=sc.EV_DISTANCE_TO_EMPTY,
        translation_key="ev_range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SubaruSensorEntityDescription(
        key=sc.EV_STATE_OF_CHARGE_PERCENT,
        translation_key="ev_battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SubaruSensorEntityDescription(
        key=sc.EV_TIME_TO_FULLY_CHARGED_UTC,
        translation_key="ev_time_to_full_charge",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SubaruConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Subaru sensors by config_entry."""
    coordinator = config_entry.runtime_data.coordinator
    vehicle_info = config_entry.runtime_data.vehicles
    entities = []
    await _async_migrate_entries(hass, config_entry)
    for info in vehicle_info.values():
        entities.extend(create_vehicle_sensors(info, coordinator))
    async_add_entities(entities)


def create_vehicle_sensors(
    vehicle_info, coordinator: SubaruDataUpdateCoordinator
) -> list[SubaruSensor]:
    """Instantiate all available sensors for the vehicle."""
    sensor_descriptions_to_add = []
    sensor_descriptions_to_add.extend(SAFETY_SENSORS)

    if vehicle_info[VEHICLE_API_GEN] in [API_GEN_2, API_GEN_3, API_GEN_4]:
        sensor_descriptions_to_add.extend(API_GEN_2_SENSORS)

    if vehicle_info[VEHICLE_API_GEN] in [API_GEN_3, API_GEN_4]:
        sensor_descriptions_to_add.extend(API_GEN_3_SENSORS)

    if vehicle_info[VEHICLE_HAS_EV]:
        sensor_descriptions_to_add.extend(EV_SENSORS)

    return [
        SubaruSensor(
            vehicle_info,
            coordinator,
            description,
        )
        for description in sensor_descriptions_to_add
    ]


class SubaruSensor(SubaruCoordinatorEntity, SensorEntity):
    """Class for Subaru sensors."""

    entity_description: SubaruSensorEntityDescription

    def __init__(
        self,
        vehicle_info: dict,
        coordinator: SubaruDataUpdateCoordinator,
        description: SubaruSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle_info, coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the state of the sensor."""
        vehicle_data = self.coordinator.data[self.vin]
        if self.entity_description.value_fn is not None:
            current_value = self.entity_description.value_fn(vehicle_data)
        else:
            current_value = vehicle_data[VEHICLE_STATUS].get(
                self.entity_description.key
            )

        if (
            self.entity_description.key == sc.AVG_FUEL_CONSUMPTION
            and isinstance(current_value, (int, float))
            and current_value > 0
            and self.hass.config.units == METRIC_SYSTEM
        ):
            return round((100.0 * L_PER_GAL) / (KM_PER_MI * current_value), 1)

        return current_value

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit_of_measurement of the device."""
        if (
            self.entity_description.key == sc.AVG_FUEL_CONSUMPTION
            and self.hass.config.units == METRIC_SYSTEM
        ):
            return FUEL_CONSUMPTION_LITERS_PER_HUNDRED_KILOMETERS
        return self.entity_description.native_unit_of_measurement


async def _async_migrate_entries(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Migrate sensor entries from HA<=2022.10 to use preferred unique_id."""
    entity_registry = er.async_get(hass)

    replacements = {
        "ODOMETER": sc.ODOMETER,
        "AVG FUEL CONSUMPTION": sc.AVG_FUEL_CONSUMPTION,
        "RANGE": sc.DIST_TO_EMPTY,
        "TIRE PRESSURE FL": sc.TIRE_PRESSURE_FL,
        "TIRE PRESSURE FR": sc.TIRE_PRESSURE_FR,
        "TIRE PRESSURE RL": sc.TIRE_PRESSURE_RL,
        "TIRE PRESSURE RR": sc.TIRE_PRESSURE_RR,
        "FUEL LEVEL": sc.REMAINING_FUEL_PERCENT,
        "EV RANGE": sc.EV_DISTANCE_TO_EMPTY,
        "EV BATTERY LEVEL": sc.EV_STATE_OF_CHARGE_PERCENT,
        "EV TIME TO FULL CHARGE": sc.EV_TIME_TO_FULLY_CHARGED_UTC,
    }

    @callback
    def update_unique_id(entry: er.RegistryEntry) -> dict[str, Any] | None:
        id_split = entry.unique_id.split("_")
        key = id_split[1].upper() if len(id_split) == 2 else None

        if key not in replacements or id_split[1] == replacements[key]:
            return None

        new_unique_id = entry.unique_id.replace(id_split[1], replacements[key])
        _LOGGER.debug(
            "Migrating entity '%s' unique_id from '%s' to '%s'",
            entry.entity_id,
            entry.unique_id,
            new_unique_id,
        )
        if existing_entity_id := entity_registry.async_get_entity_id(
            entry.domain, entry.platform, new_unique_id
        ):
            _LOGGER.debug(
                "Cannot migrate to unique_id '%s', already exists for '%s'",
                new_unique_id,
                existing_entity_id,
            )
            return None
        return {
            "new_unique_id": new_unique_id,
        }

    await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)
