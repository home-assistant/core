"""Support for sensors through the SmartThings cloud API."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pysmartthings import Attribute, Capability
from pysmartthings.device import DeviceEntity, DeviceStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfArea,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DATA_BROKERS, DOMAIN
from .entity import SmartThingsEntity


def power_attributes(status: DeviceStatus) -> dict[str, Any]:
    """Return the power attributes."""
    state = {}
    for attribute in ("power_consumption_start", "power_consumption_end"):
        value = getattr(status, attribute)
        if value is not None:
            state[attribute] = value
    return state


@dataclass(frozen=True, kw_only=True)
class SmartThingsSensorEntityDescription(SensorEntityDescription):
    """Describe a SmartThings sensor entity."""

    value_fn: Callable[[Any], str | float | int | datetime | None] = lambda value: value
    extra_state_attributes_fn: Callable[[DeviceStatus], dict[str, Any]] | None = None
    unique_id_separator: str = "."


CAPABILITY_TO_SENSORS: dict[
    str, dict[str, list[SmartThingsSensorEntityDescription]]
] = {
    Capability.activity_lighting_mode: {
        Attribute.lighting_mode: [
            SmartThingsSensorEntityDescription(
                key=Attribute.lighting_mode,
                name="Activity Lighting Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.air_conditioner_mode: {
        Attribute.air_conditioner_mode: [
            SmartThingsSensorEntityDescription(
                key=Attribute.air_conditioner_mode,
                name="Air Conditioner Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.air_quality_sensor: {
        Attribute.air_quality: [
            SmartThingsSensorEntityDescription(
                key=Attribute.air_quality,
                name="Air Quality",
                native_unit_of_measurement="CAQI",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.alarm: {
        Attribute.alarm: [
            SmartThingsSensorEntityDescription(
                key=Attribute.alarm,
                name="Alarm",
            )
        ]
    },
    Capability.audio_volume: {
        Attribute.volume: [
            SmartThingsSensorEntityDescription(
                key=Attribute.volume,
                name="Volume",
                native_unit_of_measurement=PERCENTAGE,
            )
        ]
    },
    Capability.battery: {
        Attribute.battery: [
            SmartThingsSensorEntityDescription(
                key=Attribute.battery,
                name="Battery",
                native_unit_of_measurement=PERCENTAGE,
                device_class=SensorDeviceClass.BATTERY,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.body_mass_index_measurement: {
        Attribute.bmi_measurement: [
            SmartThingsSensorEntityDescription(
                key=Attribute.bmi_measurement,
                name="Body Mass Index",
                native_unit_of_measurement=f"{UnitOfMass.KILOGRAMS}/{UnitOfArea.SQUARE_METERS}",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.body_weight_measurement: {
        Attribute.body_weight_measurement: [
            SmartThingsSensorEntityDescription(
                key=Attribute.body_weight_measurement,
                name="Body Weight",
                native_unit_of_measurement=UnitOfMass.KILOGRAMS,
                device_class=SensorDeviceClass.WEIGHT,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.carbon_dioxide_measurement: {
        Attribute.carbon_dioxide: [
            SmartThingsSensorEntityDescription(
                key=Attribute.carbon_dioxide,
                name="Carbon Dioxide",
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.carbon_monoxide_detector: {
        Attribute.carbon_monoxide: [
            SmartThingsSensorEntityDescription(
                key=Attribute.carbon_monoxide,
                name="Carbon Monoxide Detector",
            )
        ]
    },
    Capability.carbon_monoxide_measurement: {
        Attribute.carbon_monoxide_level: [
            SmartThingsSensorEntityDescription(
                key=Attribute.carbon_monoxide_level,
                name="Carbon Monoxide Level",
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.dishwasher_operating_state: {
        Attribute.machine_state: [
            SmartThingsSensorEntityDescription(
                key=Attribute.machine_state,
                name="Dishwasher Machine State",
            )
        ],
        Attribute.dishwasher_job_state: [
            SmartThingsSensorEntityDescription(
                key=Attribute.dishwasher_job_state,
                name="Dishwasher Job State",
            )
        ],
        Attribute.completion_time: [
            SmartThingsSensorEntityDescription(
                key=Attribute.completion_time,
                name="Dishwasher Completion Time",
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
    },
    Capability.dryer_mode: {
        Attribute.dryer_mode: [
            SmartThingsSensorEntityDescription(
                key=Attribute.dryer_mode,
                name="Dryer Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.dryer_operating_state: {
        Attribute.machine_state: [
            SmartThingsSensorEntityDescription(
                key=Attribute.machine_state,
                name="Dryer Machine State",
            )
        ],
        Attribute.dryer_job_state: [
            SmartThingsSensorEntityDescription(
                key=Attribute.dryer_job_state,
                name="Dryer Job State",
            )
        ],
        Attribute.completion_time: [
            SmartThingsSensorEntityDescription(
                key=Attribute.completion_time,
                name="Dryer Completion Time",
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
    },
    Capability.dust_sensor: {
        Attribute.fine_dust_level: [
            SmartThingsSensorEntityDescription(
                key=Attribute.fine_dust_level,
                name="Fine Dust Level",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
        Attribute.dust_level: [
            SmartThingsSensorEntityDescription(
                key=Attribute.dust_level,
                name="Dust Level",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
    },
    Capability.energy_meter: {
        Attribute.energy: [
            SmartThingsSensorEntityDescription(
                key=Attribute.energy,
                name="Energy Meter",
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
            )
        ]
    },
    Capability.equivalent_carbon_dioxide_measurement: {
        Attribute.equivalent_carbon_dioxide_measurement: [
            SmartThingsSensorEntityDescription(
                key=Attribute.equivalent_carbon_dioxide_measurement,
                name="Equivalent Carbon Dioxide Measurement",
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.formaldehyde_measurement: {
        Attribute.formaldehyde_level: [
            SmartThingsSensorEntityDescription(
                key=Attribute.formaldehyde_level,
                name="Formaldehyde Measurement",
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.gas_meter: {
        Attribute.gas_meter: [
            SmartThingsSensorEntityDescription(
                key=Attribute.gas_meter,
                name="Gas Meter",
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
        Attribute.gas_meter_calorific: [
            SmartThingsSensorEntityDescription(
                key=Attribute.gas_meter_calorific,
                name="Gas Meter Calorific",
            )
        ],
        Attribute.gas_meter_time: [
            SmartThingsSensorEntityDescription(
                key=Attribute.gas_meter_time,
                name="Gas Meter Time",
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
        Attribute.gas_meter_volume: [
            SmartThingsSensorEntityDescription(
                key=Attribute.gas_meter_volume,
                name="Gas Meter Volume",
                native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
                device_class=SensorDeviceClass.GAS,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
    },
    Capability.illuminance_measurement: {
        Attribute.illuminance: [
            SmartThingsSensorEntityDescription(
                key=Attribute.illuminance,
                name="Illuminance",
                native_unit_of_measurement=LIGHT_LUX,
                device_class=SensorDeviceClass.ILLUMINANCE,
            )
        ]
    },
    Capability.infrared_level: {
        Attribute.infrared_level: [
            SmartThingsSensorEntityDescription(
                key=Attribute.infrared_level,
                name="Infrared Level",
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.media_input_source: {
        Attribute.input_source: [
            SmartThingsSensorEntityDescription(
                key=Attribute.input_source,
                name="Media Input Source",
            )
        ]
    },
    Capability.media_playback_repeat: {
        Attribute.playback_repeat_mode: [
            SmartThingsSensorEntityDescription(
                key=Attribute.playback_repeat_mode,
                name="Media Playback Repeat",
            )
        ]
    },
    Capability.media_playback_shuffle: {
        Attribute.playback_shuffle: [
            SmartThingsSensorEntityDescription(
                key=Attribute.playback_shuffle,
                name="Media Playback Shuffle",
            )
        ]
    },
    Capability.media_playback: {
        Attribute.playback_status: [
            SmartThingsSensorEntityDescription(
                key=Attribute.playback_status,
                name="Media Playback Status",
            )
        ]
    },
    Capability.odor_sensor: {
        Attribute.odor_level: [
            SmartThingsSensorEntityDescription(
                key=Attribute.odor_level,
                name="Odor Sensor",
            )
        ]
    },
    Capability.oven_mode: {
        Attribute.oven_mode: [
            SmartThingsSensorEntityDescription(
                key=Attribute.oven_mode,
                name="Oven Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.oven_operating_state: {
        Attribute.machine_state: [
            SmartThingsSensorEntityDescription(
                key=Attribute.machine_state,
                name="Oven Machine State",
            )
        ],
        Attribute.oven_job_state: [
            SmartThingsSensorEntityDescription(
                key=Attribute.oven_job_state,
                name="Oven Job State",
            )
        ],
        Attribute.completion_time: [
            SmartThingsSensorEntityDescription(
                key=Attribute.completion_time,
                name="Oven Completion Time",
            )
        ],
    },
    Capability.oven_setpoint: {
        Attribute.oven_setpoint: [
            SmartThingsSensorEntityDescription(
                key=Attribute.oven_setpoint,
                name="Oven Set Point",
            )
        ]
    },
    Capability.power_consumption_report: {
        Attribute.power_consumption: [
            SmartThingsSensorEntityDescription(
                key="energy_meter",
                name="energy",
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: (
                    val / 1000 if (val := value.get("energy")) is not None else None
                ),
            ),
            SmartThingsSensorEntityDescription(
                key="power_meter",
                name="power",
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement=UnitOfPower.WATT,
                value_fn=lambda value: value.get("power"),
                extra_state_attributes_fn=power_attributes,
            ),
            SmartThingsSensorEntityDescription(
                key="deltaEnergy_meter",
                name="deltaEnergy",
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: (
                    val / 1000
                    if (val := value.get("deltaEnergy")) is not None
                    else None
                ),
            ),
            SmartThingsSensorEntityDescription(
                key="powerEnergy_meter",
                name="powerEnergy",
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: (
                    val / 1000
                    if (val := value.get("powerEnergy")) is not None
                    else None
                ),
            ),
            SmartThingsSensorEntityDescription(
                key="energySaved_meter",
                name="energySaved",
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: (
                    val / 1000
                    if (val := value.get("energySaved")) is not None
                    else None
                ),
            ),
        ]
    },
    Capability.power_meter: {
        Attribute.power: [
            SmartThingsSensorEntityDescription(
                key=Attribute.power,
                name="Power Meter",
                native_unit_of_measurement=UnitOfPower.WATT,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.power_source: {
        Attribute.power_source: [
            SmartThingsSensorEntityDescription(
                key=Attribute.power_source,
                name="Power Source",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.refrigeration_setpoint: {
        Attribute.refrigeration_setpoint: [
            SmartThingsSensorEntityDescription(
                key=Attribute.refrigeration_setpoint,
                name="Refrigeration Setpoint",
            )
        ]
    },
    Capability.relative_humidity_measurement: {
        Attribute.humidity: [
            SmartThingsSensorEntityDescription(
                key=Attribute.humidity,
                name="Relative Humidity",
                native_unit_of_measurement=PERCENTAGE,
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.robot_cleaner_cleaning_mode: {
        Attribute.robot_cleaner_cleaning_mode: [
            SmartThingsSensorEntityDescription(
                key=Attribute.robot_cleaner_cleaning_mode,
                name="Robot Cleaner Cleaning Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.robot_cleaner_movement: {
        Attribute.robot_cleaner_movement: [
            SmartThingsSensorEntityDescription(
                key=Attribute.robot_cleaner_movement,
                name="Robot Cleaner Movement",
            )
        ]
    },
    Capability.robot_cleaner_turbo_mode: {
        Attribute.robot_cleaner_turbo_mode: [
            SmartThingsSensorEntityDescription(
                key=Attribute.robot_cleaner_turbo_mode,
                name="Robot Cleaner Turbo Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.signal_strength: {
        Attribute.lqi: [
            SmartThingsSensorEntityDescription(
                key=Attribute.lqi,
                name="LQI Signal Strength",
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ],
        Attribute.rssi: [
            SmartThingsSensorEntityDescription(
                key=Attribute.rssi,
                name="RSSI Signal Strength",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ],
    },
    Capability.smoke_detector: {
        Attribute.smoke: [
            SmartThingsSensorEntityDescription(
                key=Attribute.smoke,
                name="Smoke Detector",
            )
        ]
    },
    Capability.temperature_measurement: {
        Attribute.temperature: [
            SmartThingsSensorEntityDescription(
                key=Attribute.temperature,
                name="Temperature Measurement",
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.thermostat_cooling_setpoint: {
        Attribute.cooling_setpoint: [
            SmartThingsSensorEntityDescription(
                key=Attribute.cooling_setpoint,
                name="Thermostat Cooling Setpoint",
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            )
        ]
    },
    Capability.thermostat_fan_mode: {
        Attribute.thermostat_fan_mode: [
            SmartThingsSensorEntityDescription(
                key=Attribute.thermostat_fan_mode,
                name="Thermostat Fan Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.thermostat_heating_setpoint: {
        Attribute.heating_setpoint: [
            SmartThingsSensorEntityDescription(
                key=Attribute.heating_setpoint,
                name="Thermostat Heating Setpoint",
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.thermostat_mode: {
        Attribute.thermostat_mode: [
            SmartThingsSensorEntityDescription(
                key=Attribute.thermostat_mode,
                name="Thermostat Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.thermostat_operating_state: {
        Attribute.thermostat_operating_state: [
            SmartThingsSensorEntityDescription(
                key=Attribute.thermostat_operating_state,
                name="Thermostat Operating State",
            )
        ]
    },
    Capability.thermostat_setpoint: {
        Attribute.thermostat_setpoint: [
            SmartThingsSensorEntityDescription(
                key=Attribute.thermostat_setpoint,
                name="Thermostat Setpoint",
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.three_axis: {
        Attribute.three_axis: [
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
    Capability.tv_channel: {
        Attribute.tv_channel: [
            SmartThingsSensorEntityDescription(
                key=Attribute.tv_channel,
                name="Tv Channel",
            )
        ],
        Attribute.tv_channel_name: [
            SmartThingsSensorEntityDescription(
                key=Attribute.tv_channel_name,
                name="Tv Channel Name",
            )
        ],
    },
    Capability.tvoc_measurement: {
        Attribute.tvoc_level: [
            SmartThingsSensorEntityDescription(
                key=Attribute.tvoc_level,
                name="Tvoc Measurement",
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.ultraviolet_index: {
        Attribute.ultraviolet_index: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ultraviolet_index,
                name="Ultraviolet Index",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.voltage_measurement: {
        Attribute.voltage: [
            SmartThingsSensorEntityDescription(
                key=Attribute.voltage,
                name="Voltage Measurement",
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                device_class=SensorDeviceClass.VOLTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.washer_mode: {
        Attribute.washer_mode: [
            SmartThingsSensorEntityDescription(
                key=Attribute.washer_mode,
                name="Washer Mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.washer_operating_state: {
        Attribute.machine_state: [
            SmartThingsSensorEntityDescription(
                key=Attribute.machine_state,
                name="Washer Machine State",
            )
        ],
        Attribute.washer_job_state: [
            SmartThingsSensorEntityDescription(
                key=Attribute.washer_job_state,
                name="Washer Job State",
            )
        ],
        Attribute.completion_time: [
            SmartThingsSensorEntityDescription(
                key=Attribute.completion_time,
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
    "mG": None,  # Three axis sensors never had a unit, so this removes it for now
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        SmartThingsSensor(device, attribute, description)
        for device in broker.devices.values()
        for capability in broker.get_assigned(device.device_id, "sensor")
        for attribute, descriptions in CAPABILITY_TO_SENSORS[capability].items()
        for description in descriptions
    )


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    return [
        capability for capability in CAPABILITY_TO_SENSORS if capability in capabilities
    ]


class SmartThingsSensor(SmartThingsEntity, SensorEntity):
    """Define a SmartThings Sensor."""

    entity_description: SmartThingsSensorEntityDescription

    def __init__(
        self,
        device: DeviceEntity,
        attribute: str,
        entity_description: SmartThingsSensorEntityDescription,
    ) -> None:
        """Init the class."""
        super().__init__(device)
        self._attribute = attribute
        self._attr_name = f"{device.label} {entity_description.name}"
        self._attr_unique_id = f"{device.device_id}{entity_description.unique_id_separator}{entity_description.key}"
        self.entity_description = entity_description

    @property
    def native_value(self) -> str | float | int | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self._device.status.attributes[self._attribute].value
        )

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        unit = self._device.status.attributes[self._attribute].unit
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
                self._device.status
            )
        return None
