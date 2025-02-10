"""Support for sensors through the SmartThings cloud API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pysmartthings.models import Attribute, Capability

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SmartThingsConfigEntry, SmartThingsDeviceCoordinator
from .entity import SmartThingsEntity

# class Map(NamedTuple):
#     """Tuple for mapping Smartthings capabilities to Home Assistant sensors."""
#
#     attribute: str
#     name: str
#     default_unit: str | None
#     device_class: SensorDeviceClass | None
#     state_class: SensorStateClass | None
#     entity_category: EntityCategory | None
#
#
# CAPABILITY_TO_SENSORS: dict[str, list[Map]] = {
#     Capability.activity_lighting_mode: [
#         Map(
#             Attribute.lighting_mode,
#             "Activity Lighting Mode",
#             None,
#             None,
#             None,
#             EntityCategory.DIAGNOSTIC,
#         )
#     ],
#     Capability.air_conditioner_mode: [
#         Map(
#             Attribute.air_conditioner_mode,
#             "Air Conditioner Mode",
#             None,
#             None,
#             None,
#             EntityCategory.DIAGNOSTIC,
#         )
#     ],
#     Capability.body_mass_index_measurement: [
#         Map(
#             Attribute.bmi_measurement,
#             "Body Mass Index",
#             f"{UnitOfMass.KILOGRAMS}/{UnitOfArea.SQUARE_METERS}",
#             None,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
#     Capability.body_weight_measurement: [
#         Map(
#             Attribute.body_weight_measurement,
#             "Body Weight",
#             UnitOfMass.KILOGRAMS,
#             SensorDeviceClass.WEIGHT,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
#     Capability.carbon_dioxide_measurement: [
#         Map(
#             Attribute.carbon_dioxide,
#             "Carbon Dioxide Measurement",
#             CONCENTRATION_PARTS_PER_MILLION,
#             SensorDeviceClass.CO2,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
#     Capability.carbon_monoxide_detector: [
#         Map(
#             Attribute.carbon_monoxide,
#             "Carbon Monoxide Detector",
#             None,
#             None,
#             None,
#             None,
#         )
#     ],
#     Capability.carbon_monoxide_measurement: [
#         Map(
#             Attribute.carbon_monoxide_level,
#             "Carbon Monoxide Measurement",
#             CONCENTRATION_PARTS_PER_MILLION,
#             SensorDeviceClass.CO,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
#     Capability.dryer_mode: [
#         Map(
#             Attribute.dryer_mode,
#             "Dryer Mode",
#             None,
#             None,
#             None,
#             EntityCategory.DIAGNOSTIC,
#         )
#     ],
#     Capability.equivalent_carbon_dioxide_measurement: [
#         Map(
#             Attribute.equivalent_carbon_dioxide_measurement,
#             "Equivalent Carbon Dioxide Measurement",
#             CONCENTRATION_PARTS_PER_MILLION,
#             SensorDeviceClass.CO2,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
#     Capability.formaldehyde_measurement: [
#         Map(
#             Attribute.formaldehyde_level,
#             "Formaldehyde Measurement",
#             CONCENTRATION_PARTS_PER_MILLION,
#             None,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
#     Capability.gas_meter: [
#         Map(
#             Attribute.gas_meter,
#             "Gas Meter",
#             UnitOfEnergy.KILO_WATT_HOUR,
#             SensorDeviceClass.ENERGY,
#             SensorStateClass.MEASUREMENT,
#             None,
#         ),
#         Map(
#             Attribute.gas_meter_calorific, "Gas Meter Calorific", None, None, None, None
#         ),
#         Map(
#             Attribute.gas_meter_time,
#             "Gas Meter Time",
#             None,
#             SensorDeviceClass.TIMESTAMP,
#             None,
#             None,
#         ),
#         Map(
#             Attribute.gas_meter_volume,
#             "Gas Meter Volume",
#             UnitOfVolume.CUBIC_METERS,
#             SensorDeviceClass.GAS,
#             SensorStateClass.MEASUREMENT,
#             None,
#         ),
#     ],
#     Capability.illuminance_measurement: [
#         Map(
#             Attribute.illuminance,
#             "Illuminance",
#             LIGHT_LUX,
#             SensorDeviceClass.ILLUMINANCE,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
#     Capability.infrared_level: [
#         Map(
#             Attribute.infrared_level,
#             "Infrared Level",
#             PERCENTAGE,
#             None,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
#     Capability.media_playback_repeat: [
#         Map(
#             Attribute.playback_repeat_mode,
#             "Media Playback Repeat",
#             None,
#             None,
#             None,
#             None,
#         )
#     ],
#     Capability.media_playback_shuffle: [
#         Map(
#             Attribute.playback_shuffle, "Media Playback Shuffle", None, None, None, None
#         )
#     ],
#     Capability.oven_setpoint: [
#         Map(Attribute.oven_setpoint, "Oven Set Point", None, None, None, None)
#     ],
#     Capability.power_source: [
#         Map(
#             Attribute.power_source,
#             "Power Source",
#             None,
#             None,
#             None,
#             EntityCategory.DIAGNOSTIC,
#         )
#     ],
#     Capability.refrigeration_setpoint: [
#         Map(
#             Attribute.refrigeration_setpoint,
#             "Refrigeration Setpoint",
#             None,
#             SensorDeviceClass.TEMPERATURE,
#             None,
#             None,
#         )
#     ],
#     Capability.signal_strength: [
#         Map(
#             Attribute.lqi,
#             "LQI Signal Strength",
#             None,
#             None,
#             SensorStateClass.MEASUREMENT,
#             EntityCategory.DIAGNOSTIC,
#         ),
#         Map(
#             Attribute.rssi,
#             "RSSI Signal Strength",
#             None,
#             SensorDeviceClass.SIGNAL_STRENGTH,
#             SensorStateClass.MEASUREMENT,
#             EntityCategory.DIAGNOSTIC,
#         ),
#     ],
#     Capability.smoke_detector: [
#         Map(Attribute.smoke, "Smoke Detector", None, None, None, None)
#     ],
#     Capability.thermostat_fan_mode: [
#         Map(
#             Attribute.thermostat_fan_mode,
#             "Thermostat Fan Mode",
#             None,
#             None,
#             None,
#             EntityCategory.DIAGNOSTIC,
#         )
#     ],
#     Capability.thermostat_heating_setpoint: [
#         Map(
#             Attribute.heating_setpoint,
#             "Thermostat Heating Setpoint",
#             None,
#             SensorDeviceClass.TEMPERATURE,
#             None,
#             EntityCategory.DIAGNOSTIC,
#         )
#     ],
#     Capability.thermostat_mode: [
#         Map(
#             Attribute.thermostat_mode,
#             "Thermostat Mode",
#             None,
#             None,
#             None,
#             EntityCategory.DIAGNOSTIC,
#         )
#     ],
#     Capability.thermostat_operating_state: [
#         Map(
#             Attribute.thermostat_operating_state,
#             "Thermostat Operating State",
#             None,
#             None,
#             None,
#             None,
#         )
#     ],
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
#     Capability.tvoc_measurement: [
#         Map(
#             Attribute.tvoc_level,
#             "Tvoc Measurement",
#             CONCENTRATION_PARTS_PER_MILLION,
#             None,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
#     Capability.ultraviolet_index: [
#         Map(
#             Attribute.ultraviolet_index,
#             "Ultraviolet Index",
#             None,
#             None,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
#     Capability.voltage_measurement: [
#         Map(
#             Attribute.voltage,
#             "Voltage Measurement",
#             UnitOfElectricPotential.VOLT,
#             SensorDeviceClass.VOLTAGE,
#             SensorStateClass.MEASUREMENT,
#             None,
#         )
#     ],
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
# }


@dataclass(frozen=True, kw_only=True)
class SmartThingsSensorEntityDescription(SensorEntityDescription):
    """Describe a SmartThings sensor entity."""

    value_fn: Callable[[Any], str | float | int | datetime | None] = lambda value: value
    extra_state_attributes: Callable[[Any], dict[str, Any]] | None = None
    unique_id_separator: str = "."
    capability_ignore_list: set[Capability] | None = None


CAPABILITY_TO_SENSORS: dict[
    Capability, dict[Attribute, list[SmartThingsSensorEntityDescription]]
] = {
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
    Capability.MEDIA_PLAYBACK: {
        Attribute.PLAYBACK_STATUS: [
            SmartThingsSensorEntityDescription(
                key=Attribute.PLAYBACK_STATUS,
                name="Media Playback Status",
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
    Capability.THERMOSTAT_COOLING_SETPOINT: {
        Attribute.COOLING_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COOLING_SETPOINT,
                name="Thermostat Cooling Setpoint",
                device_class=SensorDeviceClass.TEMPERATURE,
                capability_ignore_list={Capability.AIR_CONDITIONER_MODE},
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
    Capability.MEDIA_INPUT_SOURCE: {
        Attribute.INPUT_SOURCE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.INPUT_SOURCE,
                name="Media Input Source",
            )
        ]
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for a config entry."""
    devices = entry.runtime_data.devices
    async_add_entities(
        SmartThingsSensor(device, description, capability, attribute)
        for device in devices
        for capability, attributes in device.data.items()
        if capability in CAPABILITY_TO_SENSORS
        for attribute in attributes
        for description in CAPABILITY_TO_SENSORS[capability].get(attribute, [])
        if not description.capability_ignore_list
        or not any(
            capability in device.data
            for capability in description.capability_ignore_list
        )
    )
    # broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    # entities: list[SensorEntity] = []
    # for device in broker.devices.values():
    #     for capability in broker.get_assigned(device.device_id, "sensor"):
    #         else:
    #             maps = CAPABILITY_TO_SENSORS[capability]
    #             entities.extend(
    #                 [
    #                     SmartThingsSensor(
    #                         device,
    #                         m.attribute,
    #                         m.name,
    #                         m.default_unit,
    #                         m.device_class,
    #                         m.state_class,
    #                         m.entity_category,
    #                     )
    #                     for m in maps
    #                 ]
    #             )
    #
    # async_add_entities(entities)


# def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
#     """Return all capabilities supported if minimum required are present."""
#     return [
#         capability for capability in CAPABILITY_TO_SENSORS if capability in capabilities
#     ]


class SmartThingsSensor(SmartThingsEntity, SensorEntity):
    """Define a SmartThings Sensor."""

    entity_description: SmartThingsSensorEntityDescription

    def __init__(
        self,
        device: SmartThingsDeviceCoordinator,
        entity_description: SmartThingsSensorEntityDescription,
        capability: Capability,
        attribute: Attribute,
    ) -> None:
        """Init the class."""
        super().__init__(device)
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
        unit = self.coordinator.data[self.capability][self._attribute].unit
        return (
            UNITS.get(unit, unit)
            if unit
            else self.entity_description.native_unit_of_measurement
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.extra_state_attributes:
            return self.entity_description.extra_state_attributes(
                self.get_attribute_value(self.capability, self._attribute)
            )
        return None
