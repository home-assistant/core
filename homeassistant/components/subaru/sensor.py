"""Support for Subaru sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any

import subarulink.const as sc

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfPressure, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_conversion import DistanceConverter, VolumeConverter
from homeassistant.util.unit_system import METRIC_SYSTEM

from . import get_device_info
from .const import (
    API_GEN_2,
    API_GEN_3,
    API_GEN_4,
    VEHICLE_API_GEN,
    VEHICLE_HAS_EV,
    VEHICLE_HEALTH,
    VEHICLE_STATUS,
    VEHICLE_VIN,
)
from .coordinator import SubaruConfigEntry, SubaruDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


# Fuel consumption units
FUEL_CONSUMPTION_LITERS_PER_HUNDRED_KILOMETERS = "L/100km"
FUEL_CONSUMPTION_MILES_PER_GALLON = "mi/gal"

L_PER_GAL = VolumeConverter.convert(1, UnitOfVolume.GALLONS, UnitOfVolume.LITERS)
KM_PER_MI = DistanceConverter.convert(1, UnitOfLength.MILES, UnitOfLength.KILOMETERS)

# Dict keys returned by subarulink controller.get_data(). The integration's own
# VEHICLE_STATUS / VEHICLE_HEALTH constants match the same string values.
API_KEY_VEHICLE_STATE_TYPE = "VEHICLE_STATE_TYPE"
API_KEY_EV_CHARGER_STATE_TYPE = "EV_CHARGER_STATE_TYPE"
API_KEY_EV_STATE_OF_CHARGE_MODE = "EV_STATE_OF_CHARGE_MODE"
API_KEY_RECOMMENDED_TIRE_PRESSURE = "RECOMMENDED_TIRE_PRESSURE"
API_KEY_FRONT_TIRES = "FRONT_TIRES"
API_KEY_REAR_TIRES = "REAR_TIRES"


@dataclass(frozen=True, kw_only=True)
class SubaruSensorEntityDescription(SensorEntityDescription):
    """Describes a Subaru sensor entity.

    value_fn is used for sensors that read from somewhere other than
    vehicle_status (e.g. nested values in vehicle_health). When None, the
    sensor reads vehicle_status[key].
    """

    value_fn: (
        Callable[[dict[str, Any]], StateType | date | datetime | Decimal] | None
    ) = None


def _recommended_tire_pressure(
    side: str,
) -> Callable[[dict[str, Any]], StateType | date | datetime | Decimal]:
    """Return a getter for recommended FRONT or REAR tire pressure from vehicle_health."""

    def getter(data: dict[str, Any]) -> StateType | date | datetime | Decimal:
        health = data.get(VEHICLE_HEALTH) or {}
        recommended = health.get(API_KEY_RECOMMENDED_TIRE_PRESSURE) or {}
        return recommended.get(side)

    return getter


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
    # No SensorDeviceClass.ENUM: subarulink/const.py only documents IGNITION_ON
    # and IGNITION_OFF for this field, but the live API also returns other
    # values (engine-running, moving, transport mode). Committing to an
    # incomplete `options` list would silently mark live values as invalid.
    SubaruSensorEntityDescription(
        key=API_KEY_VEHICLE_STATE_TYPE,
        translation_key="vehicle_state",
    ),
    SubaruSensorEntityDescription(
        key="recommended_tire_pressure_front",
        translation_key="recommended_tire_pressure_front",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        value_fn=_recommended_tire_pressure(API_KEY_FRONT_TIRES),
    ),
    SubaruSensorEntityDescription(
        key="recommended_tire_pressure_rear",
        translation_key="recommended_tire_pressure_rear",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
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
    # No SensorDeviceClass.ENUM for the next two: subarulink does not document
    # the option sets for these fields. Live values observed so far include
    # CHARGING, CHARGING_STOPPED, FINISHED for the charger state and EV_MODE
    # for the charge mode, but the API likely returns more. See VEHICLE_STATE
    # comment above for the same rationale.
    SubaruSensorEntityDescription(
        key=API_KEY_EV_CHARGER_STATE_TYPE,
        translation_key="ev_charger_state",
    ),
    SubaruSensorEntityDescription(
        key=API_KEY_EV_STATE_OF_CHARGE_MODE,
        translation_key="ev_state_of_charge_mode",
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


class SubaruSensor(CoordinatorEntity[SubaruDataUpdateCoordinator], SensorEntity):
    """Class for Subaru sensors."""

    _attr_has_entity_name = True
    entity_description: SubaruSensorEntityDescription

    def __init__(
        self,
        vehicle_info: dict,
        coordinator: SubaruDataUpdateCoordinator,
        description: SubaruSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.vin = vehicle_info[VEHICLE_VIN]
        self.entity_description = description
        self._attr_device_info = get_device_info(vehicle_info)
        self._attr_unique_id = f"{self.vin}_{description.key}"

    @property
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
            and self.hass.config.units == METRIC_SYSTEM
        ):
            return round((100.0 * L_PER_GAL) / (KM_PER_MI * current_value), 1)

        return current_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit_of_measurement of the device."""
        if (
            self.entity_description.key == sc.AVG_FUEL_CONSUMPTION
            and self.hass.config.units == METRIC_SYSTEM
        ):
            return FUEL_CONSUMPTION_LITERS_PER_HUNDRED_KILOMETERS
        return self.entity_description.native_unit_of_measurement

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        last_update_success = super().available
        if last_update_success and self.vin not in self.coordinator.data:
            return False
        return last_update_success


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
