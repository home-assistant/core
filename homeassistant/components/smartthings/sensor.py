"""Support for sensors through the SmartThings cloud API."""
from __future__ import annotations

from collections import namedtuple
from collections.abc import Sequence

from pysmartthings import Attribute, Capability
from pysmartthings.device import DeviceEntity

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    AREA_SQUARE_METERS,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
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

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

Map = namedtuple("map", "attribute name default_unit device_class state_class")

CAPABILITY_TO_SENSORS = {
    Capability.activity_lighting_mode: [
        Map(Attribute.lighting_mode, "Activity Lighting Mode", None, None, None)
    ],
    Capability.air_conditioner_mode: [
        Map(Attribute.air_conditioner_mode, "Air Conditioner Mode", None, None, None)
    ],
    Capability.air_quality_sensor: [
        Map(Attribute.air_quality, "Air Quality", "CAQI", None, STATE_CLASS_MEASUREMENT)
    ],
    Capability.alarm: [Map(Attribute.alarm, "Alarm", None, None, None)],
    Capability.audio_volume: [Map(Attribute.volume, "Volume", PERCENTAGE, None, None)],
    Capability.battery: [
        Map(Attribute.battery, "Battery", PERCENTAGE, DEVICE_CLASS_BATTERY, None)
    ],
    Capability.body_mass_index_measurement: [
        Map(
            Attribute.bmi_measurement,
            "Body Mass Index",
            f"{MASS_KILOGRAMS}/{AREA_SQUARE_METERS}",
            None,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.body_weight_measurement: [
        Map(
            Attribute.body_weight_measurement,
            "Body Weight",
            MASS_KILOGRAMS,
            None,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.carbon_dioxide_measurement: [
        Map(
            Attribute.carbon_dioxide,
            "Carbon Dioxide Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            DEVICE_CLASS_CO2,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.carbon_monoxide_detector: [
        Map(Attribute.carbon_monoxide, "Carbon Monoxide Detector", None, None, None)
    ],
    Capability.carbon_monoxide_measurement: [
        Map(
            Attribute.carbon_monoxide_level,
            "Carbon Monoxide Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            DEVICE_CLASS_CO,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.dishwasher_operating_state: [
        Map(Attribute.machine_state, "Dishwasher Machine State", None, None, None),
        Map(Attribute.dishwasher_job_state, "Dishwasher Job State", None, None, None),
        Map(
            Attribute.completion_time,
            "Dishwasher Completion Time",
            None,
            DEVICE_CLASS_TIMESTAMP,
            None,
        ),
    ],
    Capability.dryer_mode: [Map(Attribute.dryer_mode, "Dryer Mode", None, None, None)],
    Capability.dryer_operating_state: [
        Map(Attribute.machine_state, "Dryer Machine State", None, None, None),
        Map(Attribute.dryer_job_state, "Dryer Job State", None, None, None),
        Map(
            Attribute.completion_time,
            "Dryer Completion Time",
            None,
            DEVICE_CLASS_TIMESTAMP,
            None,
        ),
    ],
    Capability.dust_sensor: [
        Map(
            Attribute.fine_dust_level,
            "Fine Dust Level",
            None,
            None,
            STATE_CLASS_MEASUREMENT,
        ),
        Map(Attribute.dust_level, "Dust Level", None, None, STATE_CLASS_MEASUREMENT),
    ],
    Capability.energy_meter: [
        Map(
            Attribute.energy,
            "Energy Meter",
            ENERGY_KILO_WATT_HOUR,
            DEVICE_CLASS_ENERGY,
            STATE_CLASS_TOTAL_INCREASING,
        )
    ],
    Capability.equivalent_carbon_dioxide_measurement: [
        Map(
            Attribute.equivalent_carbon_dioxide_measurement,
            "Equivalent Carbon Dioxide Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            None,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.formaldehyde_measurement: [
        Map(
            Attribute.formaldehyde_level,
            "Formaldehyde Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            None,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.gas_meter: [
        Map(
            Attribute.gas_meter,
            "Gas Meter",
            ENERGY_KILO_WATT_HOUR,
            None,
            STATE_CLASS_MEASUREMENT,
        ),
        Map(Attribute.gas_meter_calorific, "Gas Meter Calorific", None, None, None),
        Map(
            Attribute.gas_meter_time,
            "Gas Meter Time",
            None,
            DEVICE_CLASS_TIMESTAMP,
            None,
        ),
        Map(
            Attribute.gas_meter_volume,
            "Gas Meter Volume",
            VOLUME_CUBIC_METERS,
            None,
            STATE_CLASS_MEASUREMENT,
        ),
    ],
    Capability.illuminance_measurement: [
        Map(
            Attribute.illuminance,
            "Illuminance",
            LIGHT_LUX,
            DEVICE_CLASS_ILLUMINANCE,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.infrared_level: [
        Map(
            Attribute.infrared_level,
            "Infrared Level",
            PERCENTAGE,
            None,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.media_input_source: [
        Map(Attribute.input_source, "Media Input Source", None, None, None)
    ],
    Capability.media_playback_repeat: [
        Map(Attribute.playback_repeat_mode, "Media Playback Repeat", None, None, None)
    ],
    Capability.media_playback_shuffle: [
        Map(Attribute.playback_shuffle, "Media Playback Shuffle", None, None, None)
    ],
    Capability.media_playback: [
        Map(Attribute.playback_status, "Media Playback Status", None, None, None)
    ],
    Capability.odor_sensor: [
        Map(Attribute.odor_level, "Odor Sensor", None, None, None)
    ],
    Capability.oven_mode: [Map(Attribute.oven_mode, "Oven Mode", None, None, None)],
    Capability.oven_operating_state: [
        Map(Attribute.machine_state, "Oven Machine State", None, None, None),
        Map(Attribute.oven_job_state, "Oven Job State", None, None, None),
        Map(Attribute.completion_time, "Oven Completion Time", None, None, None),
    ],
    Capability.oven_setpoint: [
        Map(Attribute.oven_setpoint, "Oven Set Point", None, None, None)
    ],
    Capability.power_consumption_report: [],
    Capability.power_meter: [
        Map(
            Attribute.power,
            "Power Meter",
            POWER_WATT,
            DEVICE_CLASS_POWER,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.power_source: [
        Map(Attribute.power_source, "Power Source", None, None, None)
    ],
    Capability.refrigeration_setpoint: [
        Map(
            Attribute.refrigeration_setpoint,
            "Refrigeration Setpoint",
            None,
            DEVICE_CLASS_TEMPERATURE,
            None,
        )
    ],
    Capability.relative_humidity_measurement: [
        Map(
            Attribute.humidity,
            "Relative Humidity Measurement",
            PERCENTAGE,
            DEVICE_CLASS_HUMIDITY,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.robot_cleaner_cleaning_mode: [
        Map(
            Attribute.robot_cleaner_cleaning_mode,
            "Robot Cleaner Cleaning Mode",
            None,
            None,
            None,
        )
    ],
    Capability.robot_cleaner_movement: [
        Map(
            Attribute.robot_cleaner_movement, "Robot Cleaner Movement", None, None, None
        )
    ],
    Capability.robot_cleaner_turbo_mode: [
        Map(
            Attribute.robot_cleaner_turbo_mode,
            "Robot Cleaner Turbo Mode",
            None,
            None,
            None,
        )
    ],
    Capability.signal_strength: [
        Map(Attribute.lqi, "LQI Signal Strength", None, None, STATE_CLASS_MEASUREMENT),
        Map(
            Attribute.rssi,
            "RSSI Signal Strength",
            None,
            DEVICE_CLASS_SIGNAL_STRENGTH,
            STATE_CLASS_MEASUREMENT,
        ),
    ],
    Capability.smoke_detector: [
        Map(Attribute.smoke, "Smoke Detector", None, None, None)
    ],
    Capability.temperature_measurement: [
        Map(
            Attribute.temperature,
            "Temperature Measurement",
            None,
            DEVICE_CLASS_TEMPERATURE,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.thermostat_cooling_setpoint: [
        Map(
            Attribute.cooling_setpoint,
            "Thermostat Cooling Setpoint",
            None,
            DEVICE_CLASS_TEMPERATURE,
            None,
        )
    ],
    Capability.thermostat_fan_mode: [
        Map(Attribute.thermostat_fan_mode, "Thermostat Fan Mode", None, None, None)
    ],
    Capability.thermostat_heating_setpoint: [
        Map(
            Attribute.heating_setpoint,
            "Thermostat Heating Setpoint",
            None,
            DEVICE_CLASS_TEMPERATURE,
            None,
        )
    ],
    Capability.thermostat_mode: [
        Map(Attribute.thermostat_mode, "Thermostat Mode", None, None, None)
    ],
    Capability.thermostat_operating_state: [
        Map(
            Attribute.thermostat_operating_state,
            "Thermostat Operating State",
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
            DEVICE_CLASS_TEMPERATURE,
            None,
        )
    ],
    Capability.three_axis: [],
    Capability.tv_channel: [
        Map(Attribute.tv_channel, "Tv Channel", None, None, None),
        Map(Attribute.tv_channel_name, "Tv Channel Name", None, None, None),
    ],
    Capability.tvoc_measurement: [
        Map(
            Attribute.tvoc_level,
            "Tvoc Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            None,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.ultraviolet_index: [
        Map(
            Attribute.ultraviolet_index,
            "Ultraviolet Index",
            None,
            None,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.voltage_measurement: [
        Map(
            Attribute.voltage,
            "Voltage Measurement",
            ELECTRIC_POTENTIAL_VOLT,
            DEVICE_CLASS_VOLTAGE,
            STATE_CLASS_MEASUREMENT,
        )
    ],
    Capability.washer_mode: [
        Map(Attribute.washer_mode, "Washer Mode", None, None, None)
    ],
    Capability.washer_operating_state: [
        Map(Attribute.machine_state, "Washer Machine State", None, None, None),
        Map(Attribute.washer_job_state, "Washer Job State", None, None, None),
        Map(
            Attribute.completion_time,
            "Washer Completion Time",
            None,
            DEVICE_CLASS_TIMESTAMP,
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


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add binary sensors for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    sensors = []
    for device in broker.devices.values():
        for capability in broker.get_assigned(device.device_id, "sensor"):
            if capability == Capability.three_axis:
                sensors.extend(
                    [
                        SmartThingsThreeAxisSensor(device, index)
                        for index in range(len(THREE_AXIS_NAMES))
                    ]
                )
            elif capability == Capability.power_consumption_report:
                sensors.extend(
                    [
                        SmartThingsPowerConsumptionSensor(device, report_name)
                        for report_name in POWER_CONSUMPTION_REPORT_NAMES
                    ]
                )
            else:
                maps = CAPABILITY_TO_SENSORS[capability]
                sensors.extend(
                    [
                        SmartThingsSensor(
                            device,
                            m.attribute,
                            m.name,
                            m.default_unit,
                            m.device_class,
                            m.state_class,
                        )
                        for m in maps
                    ]
                )

        if broker.any_assigned(device.device_id, "switch"):
            for capability in (Capability.energy_meter, Capability.power_meter):
                maps = CAPABILITY_TO_SENSORS[capability]
                sensors.extend(
                    [
                        SmartThingsSensor(
                            device,
                            m.attribute,
                            m.name,
                            m.default_unit,
                            m.device_class,
                            m.state_class,
                        )
                        for m in maps
                    ]
                )

    async_add_entities(sensors)


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
    ) -> None:
        """Init the class."""
        super().__init__(device)
        self._attribute = attribute
        self._name = name
        self._device_class = device_class
        self._default_unit = default_unit
        self._attr_state_class = state_class

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return f"{self._device.label} {self._name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._device.device_id}.{self._attribute}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._device.status.attributes[self._attribute].value

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
        """Return the name of the binary sensor."""
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
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        if self.report_name != "power":
            self._attr_state_class = STATE_CLASS_TOTAL_INCREASING

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
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
            return DEVICE_CLASS_POWER
        return DEVICE_CLASS_ENERGY

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        if self.report_name == "power":
            return POWER_WATT
        return ENERGY_KILO_WATT_HOUR
