"""Support for sensors through the SmartThings cloud API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pysmartthings import Attribute, Capability, SmartThings

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfArea,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

THERMOSTAT_CAPABILITIES = {
    Capability.TEMPERATURE_MEASUREMENT,
    Capability.THERMOSTAT_HEATING_SETPOINT,
    Capability.THERMOSTAT_MODE,
}


def power_attributes(status: dict[str, Any]) -> dict[str, Any]:
    """Return the power attributes."""
    state = {}
    for attribute in ("start", "end"):
        if (value := status.get(attribute)) is not None:
            state[f"power_consumption_{attribute}"] = value
    return state


@dataclass(frozen=True, kw_only=True)
class SmartThingsSensorEntityDescription(SensorEntityDescription):
    """Describe a SmartThings sensor entity."""

    value_fn: Callable[[Any], str | float | int | datetime | None] = lambda value: value
    extra_state_attributes_fn: Callable[[Any], dict[str, Any]] | None = None
    unique_id_separator: str = "."
    capability_ignore_list: list[set[Capability]] | None = None


CAPABILITY_TO_SENSORS: dict[
    Capability, dict[Attribute, list[SmartThingsSensorEntityDescription]]
] = {
    # no fixtures
    Capability.ACTIVITY_LIGHTING_MODE: {
        Attribute.LIGHTING_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.LIGHTING_MODE,
                name="Activity Lighting Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.AIR_CONDITIONER_MODE: {
        Attribute.AIR_CONDITIONER_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.AIR_CONDITIONER_MODE,
                name="Air Conditioner Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
                capability_ignore_list=[
                    {
                        Capability.TEMPERATURE_MEASUREMENT,
                        Capability.THERMOSTAT_COOLING_SETPOINT,
                    }
                ],
            )
        ]
    },
    Capability.AIR_QUALITY_SENSOR: {
        Attribute.AIR_QUALITY: [
            SmartThingsSensorEntityDescription(
                key=Attribute.AIR_QUALITY,
                name="Air Quality",
                native_unit_of_measurement="CAQI",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.ALARM: {
        Attribute.ALARM: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ALARM,
                name="Alarm",
            )
        ]
    },
    Capability.AUDIO_VOLUME: {
        Attribute.VOLUME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.VOLUME,
                name="Volume",
                native_unit_of_measurement=PERCENTAGE,
            )
        ]
    },
    Capability.BATTERY: {
        Attribute.BATTERY: [
            SmartThingsSensorEntityDescription(
                key=Attribute.BATTERY,
                name="Battery",
                native_unit_of_measurement=PERCENTAGE,
                device_class=SensorDeviceClass.BATTERY,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    # no fixtures
    Capability.BODY_MASS_INDEX_MEASUREMENT: {
        Attribute.BMI_MEASUREMENT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.BMI_MEASUREMENT,
                name="Body Mass Index",
                native_unit_of_measurement=f"{UnitOfMass.KILOGRAMS}/{UnitOfArea.SQUARE_METERS}",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    # no fixtures
    Capability.BODY_WEIGHT_MEASUREMENT: {
        Attribute.BODY_WEIGHT_MEASUREMENT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.BODY_WEIGHT_MEASUREMENT,
                name="Body Weight",
                native_unit_of_measurement=UnitOfMass.KILOGRAMS,
                device_class=SensorDeviceClass.WEIGHT,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    # no fixtures
    Capability.CARBON_DIOXIDE_MEASUREMENT: {
        Attribute.CARBON_DIOXIDE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.CARBON_DIOXIDE,
                name="Carbon Dioxide",
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    # no fixtures
    Capability.CARBON_MONOXIDE_DETECTOR: {
        Attribute.CARBON_MONOXIDE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.CARBON_MONOXIDE,
                name="Carbon Monoxide Detector",
            )
        ]
    },
    # no fixtures
    Capability.CARBON_MONOXIDE_MEASUREMENT: {
        Attribute.CARBON_MONOXIDE_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.CARBON_MONOXIDE_LEVEL,
                name="Carbon Monoxide Level",
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.DISHWASHER_OPERATING_STATE: {
        Attribute.MACHINE_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.MACHINE_STATE,
                name="Dishwasher Machine State",
            )
        ],
        Attribute.DISHWASHER_JOB_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.DISHWASHER_JOB_STATE,
                name="Dishwasher Job State",
            )
        ],
        Attribute.COMPLETION_TIME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COMPLETION_TIME,
                name="Dishwasher Completion Time",
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
    },
    # part of the proposed spec, no fixtures
    Capability.DRYER_MODE: {
        Attribute.DRYER_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.DRYER_MODE,
                name="Dryer Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.DRYER_OPERATING_STATE: {
        Attribute.MACHINE_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.MACHINE_STATE,
                name="Dryer Machine State",
            )
        ],
        Attribute.DRYER_JOB_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.DRYER_JOB_STATE,
                name="Dryer Job State",
            )
        ],
        Attribute.COMPLETION_TIME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COMPLETION_TIME,
                name="Dryer Completion Time",
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
    },
    Capability.DUST_SENSOR: {
        Attribute.DUST_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.DUST_LEVEL,
                name="Dust Level",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
        Attribute.FINE_DUST_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.FINE_DUST_LEVEL,
                name="Fine Dust Level",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
    },
    Capability.ENERGY_METER: {
        Attribute.ENERGY: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ENERGY,
                name="Energy Meter",
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
            )
        ]
    },
    # no fixtures
    Capability.EQUIVALENT_CARBON_DIOXIDE_MEASUREMENT: {
        Attribute.EQUIVALENT_CARBON_DIOXIDE_MEASUREMENT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.EQUIVALENT_CARBON_DIOXIDE_MEASUREMENT,
                name="Equivalent Carbon Dioxide Measurement",
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    # no fixtures
    Capability.FORMALDEHYDE_MEASUREMENT: {
        Attribute.FORMALDEHYDE_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.FORMALDEHYDE_LEVEL,
                name="Formaldehyde Measurement",
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    # no fixtures
    Capability.GAS_METER: {
        Attribute.GAS_METER: [
            SmartThingsSensorEntityDescription(
                key=Attribute.GAS_METER,
                name="Gas Meter",
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
        Attribute.GAS_METER_CALORIFIC: [
            SmartThingsSensorEntityDescription(
                key=Attribute.GAS_METER_CALORIFIC,
                name="Gas Meter Calorific",
            )
        ],
        Attribute.GAS_METER_TIME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.GAS_METER_TIME,
                name="Gas Meter Time",
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
        Attribute.GAS_METER_VOLUME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.GAS_METER_VOLUME,
                name="Gas Meter Volume",
                native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
                device_class=SensorDeviceClass.GAS,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
    },
    # no fixtures
    Capability.ILLUMINANCE_MEASUREMENT: {
        Attribute.ILLUMINANCE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ILLUMINANCE,
                name="Illuminance",
                native_unit_of_measurement=LIGHT_LUX,
                device_class=SensorDeviceClass.ILLUMINANCE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    # no fixtures
    Capability.INFRARED_LEVEL: {
        Attribute.INFRARED_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.INFRARED_LEVEL,
                name="Infrared Level",
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.MEDIA_INPUT_SOURCE: {
        Attribute.INPUT_SOURCE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.INPUT_SOURCE,
                name="Media Input Source",
            )
        ]
    },
    # part of the proposed spec, no fixtures
    Capability.MEDIA_PLAYBACK_REPEAT: {
        Attribute.PLAYBACK_REPEAT_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.PLAYBACK_REPEAT_MODE,
                name="Media Playback Repeat",
            )
        ]
    },
    # part of the proposed spec, no fixtures
    Capability.MEDIA_PLAYBACK_SHUFFLE: {
        Attribute.PLAYBACK_SHUFFLE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.PLAYBACK_SHUFFLE,
                name="Media Playback Shuffle",
            )
        ]
    },
    Capability.MEDIA_PLAYBACK: {
        Attribute.PLAYBACK_STATUS: [
            SmartThingsSensorEntityDescription(
                key=Attribute.PLAYBACK_STATUS,
                name="Media Playback Status",
            )
        ]
    },
    Capability.ODOR_SENSOR: {
        Attribute.ODOR_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ODOR_LEVEL,
                name="Odor Sensor",
            )
        ]
    },
    Capability.OVEN_MODE: {
        Attribute.OVEN_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.OVEN_MODE,
                name="Oven Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.OVEN_OPERATING_STATE: {
        Attribute.MACHINE_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.MACHINE_STATE,
                name="Oven Machine State",
            )
        ],
        Attribute.OVEN_JOB_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.OVEN_JOB_STATE,
                name="Oven Job State",
            )
        ],
        Attribute.COMPLETION_TIME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COMPLETION_TIME,
                name="Oven Completion Time",
            )
        ],
    },
    Capability.OVEN_SETPOINT: {
        Attribute.OVEN_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.OVEN_SETPOINT,
                name="Oven Set Point",
            )
        ]
    },
    Capability.POWER_CONSUMPTION_REPORT: {
        Attribute.POWER_CONSUMPTION: [
            SmartThingsSensorEntityDescription(
                key="energy_meter",
                name="energy",
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: value["energy"] / 1000,
            ),
            SmartThingsSensorEntityDescription(
                key="power_meter",
                name="power",
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement=UnitOfPower.WATT,
                value_fn=lambda value: value["power"],
                extra_state_attributes_fn=power_attributes,
            ),
            SmartThingsSensorEntityDescription(
                key="deltaEnergy_meter",
                name="deltaEnergy",
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: value["deltaEnergy"] / 1000,
            ),
            SmartThingsSensorEntityDescription(
                key="powerEnergy_meter",
                name="powerEnergy",
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: value["powerEnergy"] / 1000,
            ),
            SmartThingsSensorEntityDescription(
                key="energySaved_meter",
                name="energySaved",
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: value["energySaved"] / 1000,
            ),
        ]
    },
    Capability.POWER_METER: {
        Attribute.POWER: [
            SmartThingsSensorEntityDescription(
                key=Attribute.POWER,
                name="Power Meter",
                native_unit_of_measurement=UnitOfPower.WATT,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    # no fixtures
    Capability.POWER_SOURCE: {
        Attribute.POWER_SOURCE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.POWER_SOURCE,
                name="Power Source",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    # part of the proposed spec
    Capability.REFRIGERATION_SETPOINT: {
        Attribute.REFRIGERATION_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.REFRIGERATION_SETPOINT,
                name="Refrigeration Setpoint",
                device_class=SensorDeviceClass.TEMPERATURE,
            )
        ]
    },
    Capability.RELATIVE_HUMIDITY_MEASUREMENT: {
        Attribute.HUMIDITY: [
            SmartThingsSensorEntityDescription(
                key=Attribute.HUMIDITY,
                name="Relative Humidity Measurement",
                native_unit_of_measurement=PERCENTAGE,
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.ROBOT_CLEANER_CLEANING_MODE: {
        Attribute.ROBOT_CLEANER_CLEANING_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ROBOT_CLEANER_CLEANING_MODE,
                name="Robot Cleaner Cleaning Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ],
    },
    Capability.ROBOT_CLEANER_MOVEMENT: {
        Attribute.ROBOT_CLEANER_MOVEMENT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ROBOT_CLEANER_MOVEMENT,
                name="Robot Cleaner Movement",
            )
        ]
    },
    Capability.ROBOT_CLEANER_TURBO_MODE: {
        Attribute.ROBOT_CLEANER_TURBO_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ROBOT_CLEANER_TURBO_MODE,
                name="Robot Cleaner Turbo Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    # no fixtures
    Capability.SIGNAL_STRENGTH: {
        Attribute.LQI: [
            SmartThingsSensorEntityDescription(
                key=Attribute.LQI,
                name="LQI Signal Strength",
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ],
        Attribute.RSSI: [
            SmartThingsSensorEntityDescription(
                key=Attribute.RSSI,
                name="RSSI Signal Strength",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ],
    },
    # no fixtures
    Capability.SMOKE_DETECTOR: {
        Attribute.SMOKE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.SMOKE,
                name="Smoke Detector",
            )
        ]
    },
    Capability.TEMPERATURE_MEASUREMENT: {
        Attribute.TEMPERATURE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.TEMPERATURE,
                name="Temperature Measurement",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.THERMOSTAT_COOLING_SETPOINT: {
        Attribute.COOLING_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COOLING_SETPOINT,
                name="Thermostat Cooling Setpoint",
                device_class=SensorDeviceClass.TEMPERATURE,
                capability_ignore_list=[
                    {
                        Capability.AIR_CONDITIONER_FAN_MODE,
                        Capability.TEMPERATURE_MEASUREMENT,
                        Capability.AIR_CONDITIONER_MODE,
                    },
                    THERMOSTAT_CAPABILITIES,
                ],
            )
        ]
    },
    # no fixtures
    Capability.THERMOSTAT_FAN_MODE: {
        Attribute.THERMOSTAT_FAN_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.THERMOSTAT_FAN_MODE,
                name="Thermostat Fan Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
                capability_ignore_list=[THERMOSTAT_CAPABILITIES],
            )
        ]
    },
    # no fixtures
    Capability.THERMOSTAT_HEATING_SETPOINT: {
        Attribute.HEATING_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.HEATING_SETPOINT,
                name="Thermostat Heating Setpoint",
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_category=EntityCategory.DIAGNOSTIC,
                capability_ignore_list=[THERMOSTAT_CAPABILITIES],
            )
        ]
    },
    # no fixtures
    Capability.THERMOSTAT_MODE: {
        Attribute.THERMOSTAT_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.THERMOSTAT_MODE,
                name="Thermostat Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
                capability_ignore_list=[THERMOSTAT_CAPABILITIES],
            )
        ]
    },
    # no fixtures
    Capability.THERMOSTAT_OPERATING_STATE: {
        Attribute.THERMOSTAT_OPERATING_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.THERMOSTAT_OPERATING_STATE,
                name="Thermostat Operating State",
                capability_ignore_list=[THERMOSTAT_CAPABILITIES],
            )
        ]
    },
    # deprecated capability
    #     Capability.thermostat_setpoint: [
    #         Map(
    #             Attribute.thermostat_setpoint,
    #             "Thermostat Setpoint",
    #             None,
    #             SensorDeviceClass.TEMPERATURE,
    #             None,
    #             EntityCategory.DIAGNOSTIC,
    #         )
    #     ],
    Capability.THREE_AXIS: {
        Attribute.THREE_AXIS: [
            SmartThingsSensorEntityDescription(
                key="X Coordinate",
                name="X Coordinate",
                unique_id_separator=" ",
                value_fn=lambda value: value[0],
            ),
            SmartThingsSensorEntityDescription(
                key="Y Coordinate",
                name="Y Coordinate",
                unique_id_separator=" ",
                value_fn=lambda value: value[1],
            ),
            SmartThingsSensorEntityDescription(
                key="Z Coordinate",
                name="Z Coordinate",
                unique_id_separator=" ",
                value_fn=lambda value: value[2],
            ),
        ]
    },
    Capability.TV_CHANNEL: {
        Attribute.TV_CHANNEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.TV_CHANNEL,
                name="Tv Channel",
            )
        ],
        Attribute.TV_CHANNEL_NAME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.TV_CHANNEL_NAME,
                name="Tv Channel Name",
            )
        ],
    },
    # no fixtures
    Capability.TVOC_MEASUREMENT: {
        Attribute.TVOC_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.TVOC_LEVEL,
                name="Tvoc Measurement",
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    # no fixtures
    Capability.ULTRAVIOLET_INDEX: {
        Attribute.ULTRAVIOLET_INDEX: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ULTRAVIOLET_INDEX,
                name="Ultraviolet Index",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.VOLTAGE_MEASUREMENT: {
        Attribute.VOLTAGE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.VOLTAGE,
                name="Voltage Measurement",
                device_class=SensorDeviceClass.VOLTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    # part of the proposed spec
    #     Capability.washer_mode: [
    #         Map(
    #             Attribute.washer_mode,
    #             "Washer Mode",
    #             None,
    #             None,
    #             None,
    #             EntityCategory.DIAGNOSTIC,
    #         )
    #     ],
    Capability.WASHER_OPERATING_STATE: {
        Attribute.MACHINE_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.MACHINE_STATE,
                name="Washer Machine State",
            )
        ],
        Attribute.WASHER_JOB_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.WASHER_JOB_STATE,
                name="Washer Job State",
            )
        ],
        Attribute.COMPLETION_TIME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COMPLETION_TIME,
                name="Washer Completion Time",
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
    },
}


UNITS = {
    "C": UnitOfTemperature.CELSIUS,
    "F": UnitOfTemperature.FAHRENHEIT,
    "lux": LIGHT_LUX,
    "mG": None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsSensor(entry_data.client, device, description, capability, attribute)
        for device in entry_data.devices.values()
        for capability, attributes in device.status[MAIN].items()
        if capability in CAPABILITY_TO_SENSORS
        for attribute in attributes
        for description in CAPABILITY_TO_SENSORS[capability].get(attribute, [])
        if not description.capability_ignore_list
        or not any(
            all(capability in device.status[MAIN] for capability in capability_list)
            for capability_list in description.capability_ignore_list
        )
    )


class SmartThingsSensor(SmartThingsEntity, SensorEntity):
    """Define a SmartThings Sensor."""

    entity_description: SmartThingsSensorEntityDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsSensorEntityDescription,
        capability: Capability,
        attribute: Attribute,
    ) -> None:
        """Init the class."""
        super().__init__(client, device, {capability})
        self._attr_name = f"{device.device.label} {entity_description.name}"
        self._attr_unique_id = f"{device.device.device_id}{entity_description.unique_id_separator}{entity_description.key}"
        self._attribute = attribute
        self.capability = capability
        self.entity_description = entity_description

    @property
    def native_value(self) -> str | float | datetime | int | None:
        """Return the state of the sensor."""
        res = self.get_attribute_value(self.capability, self._attribute)
        return self.entity_description.value_fn(res)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        unit = self._internal_state[self.capability][self._attribute].unit
        return (
            UNITS.get(unit, unit)
            if unit
            else self.entity_description.native_unit_of_measurement
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.extra_state_attributes_fn:
            return self.entity_description.extra_state_attributes_fn(
                self.get_attribute_value(self.capability, self._attribute)
            )
        return None
