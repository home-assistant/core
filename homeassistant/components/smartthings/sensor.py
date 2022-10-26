"""Support for sensors through the SmartThings cloud API."""
from __future__ import annotations

from collections import namedtuple
from collections.abc import Sequence

from pysmartthings import Attribute, Capability
from pysmartthings.device import DeviceEntity

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    AREA_SQUARE_METERS,
    CONCENTRATION_PARTS_PER_MILLION,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    LIGHT_LUX,
    MASS_KILOGRAMS,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

Map = namedtuple(
    "Map", "attribute name default_unit device_class state_class entity_category"
)

CAPABILITY_TO_SENSORS: dict[str, list[Map]] = {
    Capability.activity_lighting_mode: [
        Map(
            Attribute.lighting_mode,
            "Activity Lighting Mode",
            None,
            None,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.air_conditioner_mode: [
        Map(
            Attribute.air_conditioner_mode,
            "Air Conditioner Mode",
            None,
            None,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.air_quality_sensor: [
        Map(
            Attribute.air_quality,
            "Air Quality",
            "CAQI",
            None,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.alarm: [Map(Attribute.alarm, "Alarm", None, None, None, None)],
    Capability.audio_volume: [
        Map(Attribute.volume, "Volume", PERCENTAGE, None, None, None)
    ],
    Capability.battery: [
        Map(
            Attribute.battery,
            "Battery",
            PERCENTAGE,
            SensorDeviceClass.BATTERY,
            None,
            EntityCategory.DIAGNOSTIC,
        )
    ],
    Capability.body_mass_index_measurement: [
        Map(
            Attribute.bmi_measurement,
            "Body Mass Index",
            f"{MASS_KILOGRAMS}/{AREA_SQUARE_METERS}",
            None,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.body_weight_measurement: [
        Map(
            Attribute.body_weight_measurement,
            "Body Weight",
            MASS_KILOGRAMS,
            SensorDeviceClass.WEIGHT,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.carbon_dioxide_measurement: [
        Map(
            Attribute.carbon_dioxide,
            "Carbon Dioxide Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            SensorDeviceClass.CO2,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.carbon_monoxide_detector: [
        Map(
            Attribute.carbon_monoxide,
            "Carbon Monoxide Detector",
            None,
            None,
            None,
            None,
        )
    ],
    Capability.carbon_monoxide_measurement: [
        Map(
            Attribute.carbon_monoxide_level,
            "Carbon Monoxide Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            SensorDeviceClass.CO,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.dishwasher_operating_state: [
        Map(
            Attribute.machine_state, "Dishwasher Machine State", None, None, None, None
        ),
        Map(
            Attribute.dishwasher_job_state,
            "Dishwasher Job State",
            None,
            None,
            None,
            None,
        ),
        Map(
            Attribute.completion_time,
            "Dishwasher Completion Time",
            None,
            SensorDeviceClass.TIMESTAMP,
            None,
            None,
        ),
    ],
    Capability.dryer_mode: [
        Map(
            Attribute.dryer_mode,
            "Dryer Mode",
            None,
            None,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.dryer_operating_state: [
        Map(Attribute.machine_state, "Dryer Machine State", None, None, None, None),
        Map(Attribute.dryer_job_state, "Dryer Job State", None, None, None, None),
        Map(
            Attribute.completion_time,
            "Dryer Completion Time",
            None,
            SensorDeviceClass.TIMESTAMP,
            None,
            None,
        ),
    ],
    Capability.dust_sensor: [
        Map(
            Attribute.fine_dust_level,
            "Fine Dust Level",
            None,
            None,
            SensorStateClass.MEASUREMENT,
            None,
        ),
        Map(
            Attribute.dust_level,
            "Dust Level",
            None,
            None,
            SensorStateClass.MEASUREMENT,
            None,
        ),
    ],
    Capability.energy_meter: [
        Map(
            Attribute.energy,
            "Energy Meter",
            ENERGY_KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
            None,
        )
    ],
    Capability.equivalent_carbon_dioxide_measurement: [
        Map(
            Attribute.equivalent_carbon_dioxide_measurement,
            "Equivalent Carbon Dioxide Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            SensorDeviceClass.CO2,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.formaldehyde_measurement: [
        Map(
            Attribute.formaldehyde_level,
            "Formaldehyde Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            None,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.gas_meter: [
        Map(
            Attribute.gas_meter,
            "Gas Meter",
            ENERGY_KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.MEASUREMENT,
            None,
        ),
        Map(
            Attribute.gas_meter_calorific, "Gas Meter Calorific", None, None, None, None
        ),
        Map(
            Attribute.gas_meter_time,
            "Gas Meter Time",
            None,
            SensorDeviceClass.TIMESTAMP,
            None,
            None,
        ),
        Map(
            Attribute.gas_meter_volume,
            "Gas Meter Volume",
            VOLUME_CUBIC_METERS,
            SensorDeviceClass.VOLUME,
            SensorStateClass.MEASUREMENT,
            None,
        ),
    ],
    Capability.illuminance_measurement: [
        Map(
            Attribute.illuminance,
            "Illuminance",
            LIGHT_LUX,
            SensorDeviceClass.ILLUMINANCE,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.infrared_level: [
        Map(
            Attribute.infrared_level,
            "Infrared Level",
            PERCENTAGE,
            None,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.media_input_source: [
        Map(Attribute.input_source, "Media Input Source", None, None, None, None)
    ],
    Capability.media_playback_repeat: [
        Map(
            Attribute.playback_repeat_mode,
            "Media Playback Repeat",
            None,
            None,
            None,
            None,
        )
    ],
    Capability.media_playback_shuffle: [
        Map(
            Attribute.playback_shuffle, "Media Playback Shuffle", None, None, None, None
        )
    ],
    Capability.media_playback: [
        Map(Attribute.playback_status, "Media Playback Status", None, None, None, None)
    ],
    Capability.odor_sensor: [
        Map(Attribute.odor_level, "Odor Sensor", None, None, None, None)
    ],
    Capability.oven_mode: [
        Map(
            Attribute.oven_mode,
            "Oven Mode",
            None,
            None,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.oven_operating_state: [
        Map(Attribute.machine_state, "Oven Machine State", None, None, None, None),
        Map(Attribute.oven_job_state, "Oven Job State", None, None, None, None),
        Map(Attribute.completion_time, "Oven Completion Time", None, None, None, None),
    ],
    Capability.oven_setpoint: [
        Map(Attribute.oven_setpoint, "Oven Set Point", None, None, None, None)
    ],
    Capability.power_consumption_report: [],
    Capability.power_meter: [
        Map(
            Attribute.power,
            "Power Meter",
            POWER_WATT,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.power_source: [
        Map(
            Attribute.power_source,
            "Power Source",
            None,
            None,
            None,
            EntityCategory.DIAGNOSTIC,
        )
    ],
    Capability.refrigeration_setpoint: [
        Map(
            Attribute.refrigeration_setpoint,
            "Refrigeration Setpoint",
            None,
            SensorDeviceClass.TEMPERATURE,
            None,
            None,
        )
    ],
    Capability.relative_humidity_measurement: [
        Map(
            Attribute.humidity,
            "Relative Humidity Measurement",
            PERCENTAGE,
            SensorDeviceClass.HUMIDITY,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.robot_cleaner_cleaning_mode: [
        Map(
            Attribute.robot_cleaner_cleaning_mode,
            "Robot Cleaner Cleaning Mode",
            None,
            None,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.robot_cleaner_movement: [
        Map(
            Attribute.robot_cleaner_movement,
            "Robot Cleaner Movement",
            None,
            None,
            None,
            None,
        )
    ],
    Capability.robot_cleaner_turbo_mode: [
        Map(
            Attribute.robot_cleaner_turbo_mode,
            "Robot Cleaner Turbo Mode",
            None,
            None,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.signal_strength: [
        Map(
            Attribute.lqi,
            "LQI Signal Strength",
            None,
            None,
            SensorStateClass.MEASUREMENT,
            EntityCategory.DIAGNOSTIC,
        ),
        Map(
            Attribute.rssi,
            "RSSI Signal Strength",
            None,
            SensorDeviceClass.SIGNAL_STRENGTH,
            SensorStateClass.MEASUREMENT,
            EntityCategory.DIAGNOSTIC,
        ),
    ],
    Capability.smoke_detector: [
        Map(Attribute.smoke, "Smoke Detector", None, None, None, None)
    ],
    Capability.temperature_measurement: [
        Map(
            Attribute.temperature,
            "Temperature Measurement",
            None,
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.thermostat_cooling_setpoint: [
        Map(
            Attribute.cooling_setpoint,
            "Thermostat Cooling Setpoint",
            None,
            SensorDeviceClass.TEMPERATURE,
            None,
            None,
        )
    ],
    Capability.thermostat_fan_mode: [
        Map(
            Attribute.thermostat_fan_mode,
            "Thermostat Fan Mode",
            None,
            None,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.thermostat_heating_setpoint: [
        Map(
            Attribute.heating_setpoint,
            "Thermostat Heating Setpoint",
            None,
            SensorDeviceClass.TEMPERATURE,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.thermostat_mode: [
        Map(
            Attribute.thermostat_mode,
            "Thermostat Mode",
            None,
            None,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.thermostat_operating_state: [
        Map(
            Attribute.thermostat_operating_state,
            "Thermostat Operating State",
            None,
            None,
            None,
            None,
        )
    ],
    Capability.thermostat_setpoint: [
        Map(
            Attribute.thermostat_setpoint,
            "Thermostat Setpoint",
            None,
            SensorDeviceClass.TEMPERATURE,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.three_axis: [],
    Capability.tv_channel: [
        Map(Attribute.tv_channel, "Tv Channel", None, None, None, None),
        Map(Attribute.tv_channel_name, "Tv Channel Name", None, None, None, None),
    ],
    Capability.tvoc_measurement: [
        Map(
            Attribute.tvoc_level,
            "Tvoc Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            None,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.ultraviolet_index: [
        Map(
            Attribute.ultraviolet_index,
            "Ultraviolet Index",
            None,
            None,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.voltage_measurement: [
        Map(
            Attribute.voltage,
            "Voltage Measurement",
            ELECTRIC_POTENTIAL_VOLT,
            SensorDeviceClass.VOLTAGE,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.washer_mode: [
        Map(
            Attribute.washer_mode,
            "Washer Mode",
            None,
            None,
            None,
            EntityCategory.CONFIG,
        )
    ],
    Capability.washer_operating_state: [
        Map(Attribute.machine_state, "Washer Machine State", None, None, None, None),
        Map(Attribute.washer_job_state, "Washer Job State", None, None, None, None),
        Map(
            Attribute.completion_time,
            "Washer Completion Time",
            None,
            SensorDeviceClass.TIMESTAMP,
            None,
            None,
        ),
    ],
}

UNITS = {"C": TEMP_CELSIUS, "F": TEMP_FAHRENHEIT}

THREE_AXIS_NAMES = ["X Coordinate", "Y Coordinate", "Z Coordinate"]
POWER_CONSUMPTION_REPORT_NAMES = [
    "energy",
    "power",
    "deltaEnergy",
    "powerEnergy",
    "energySaved",
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    entities: list[SensorEntity] = []
    for device in broker.devices.values():
        for capability in broker.get_assigned(device.device_id, "sensor"):
            if capability == Capability.three_axis:
                entities.extend(
                    [
                        SmartThingsThreeAxisSensor(device, index)
                        for index in range(len(THREE_AXIS_NAMES))
                    ]
                )
            elif capability == Capability.power_consumption_report:
                entities.extend(
                    [
                        SmartThingsPowerConsumptionSensor(device, report_name)
                        for report_name in POWER_CONSUMPTION_REPORT_NAMES
                    ]
                )
            else:
                maps = CAPABILITY_TO_SENSORS[capability]
                entities.extend(
                    [
                        SmartThingsSensor(
                            device,
                            m.attribute,
                            m.name,
                            m.default_unit,
                            m.device_class,
                            m.state_class,
                            m.entity_category,
                        )
                        for m in maps
                    ]
                )

        if broker.any_assigned(device.device_id, "switch"):
            for capability in (Capability.energy_meter, Capability.power_meter):
                maps = CAPABILITY_TO_SENSORS[capability]
                entities.extend(
                    [
                        SmartThingsSensor(
                            device,
                            m.attribute,
                            m.name,
                            m.default_unit,
                            m.device_class,
                            m.state_class,
                            m.entity_category,
                        )
                        for m in maps
                    ]
                )

    async_add_entities(entities)


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    return [
        capability for capability in CAPABILITY_TO_SENSORS if capability in capabilities
    ]


class SmartThingsSensor(SmartThingsEntity, SensorEntity):
    """Define a SmartThings Sensor."""

    def __init__(
        self,
        device: DeviceEntity,
        attribute: str,
        name: str,
        default_unit: str,
        device_class: str,
        state_class: str | None,
        entity_category: EntityCategory | None,
    ) -> None:
        """Init the class."""
        super().__init__(device)
        self._attribute = attribute
        self._name = name
        self._device_class = device_class
        self._default_unit = default_unit
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device.label} {self._name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._device.device_id}.{self._attribute}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        value = self._device.status.attributes[self._attribute].value

        if self._device_class != SensorDeviceClass.TIMESTAMP:
            return value

        return dt_util.parse_datetime(value)

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        unit = self._device.status.attributes[self._attribute].unit
        return UNITS.get(unit, unit) if unit else self._default_unit


class SmartThingsThreeAxisSensor(SmartThingsEntity, SensorEntity):
    """Define a SmartThings Three Axis Sensor."""

    def __init__(self, device, index):
        """Init the class."""
        super().__init__(device)
        self._index = index

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device.label} {THREE_AXIS_NAMES[self._index]}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._device.device_id}.{THREE_AXIS_NAMES[self._index]}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        three_axis = self._device.status.attributes[Attribute.three_axis].value
        try:
            return three_axis[self._index]
        except (TypeError, IndexError):
            return None


class SmartThingsPowerConsumptionSensor(SmartThingsEntity, SensorEntity):
    """Define a SmartThings Sensor."""

    def __init__(
        self,
        device: DeviceEntity,
        report_name: str,
    ) -> None:
        """Init the class."""
        super().__init__(device)
        self.report_name = report_name
        self._attr_state_class = SensorStateClass.MEASUREMENT
        if self.report_name != "power":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device.label} {self.report_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._device.device_id}.{self.report_name}_meter"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        value = self._device.status.attributes[Attribute.power_consumption].value
        if value is None or value.get(self.report_name) is None:
            return None
        if self.report_name == "power":
            return value[self.report_name]
        return value[self.report_name] / 1000

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self.report_name == "power":
            return SensorDeviceClass.POWER
        return SensorDeviceClass.ENERGY

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        if self.report_name == "power":
            return POWER_WATT
        return ENERGY_KILO_WATT_HOUR

    @property
    def extra_state_attributes(self):
        """Return specific state attributes."""
        if self.report_name == "power":
            attributes = [
                "power_consumption_start",
                "power_consumption_end",
            ]
            state_attributes = {}
            for attribute in attributes:
                value = getattr(self._device.status, attribute)
                if value is not None:
                    state_attributes[attribute] = value
            return state_attributes
        return None
