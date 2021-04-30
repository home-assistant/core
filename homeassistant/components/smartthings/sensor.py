"""Support for sensors through the SmartThings cloud API."""
from __future__ import annotations

from collections import namedtuple
from collections.abc import Sequence
import logging

from pysmartthings import Attribute, Capability

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    AREA_SQUARE_METERS,
    ATTR_DATE,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    LIGHT_LUX,
    MASS_KILOGRAMS,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    VOLT,
    VOLUME_CUBIC_METERS,
)

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

_LOGGER = logging.getLogger(__name__)

Map = namedtuple("map", "attribute name default_unit device_class")

CAPABILITY_TO_SENSORS = {
    Capability.activity_lighting_mode: [
        Map(Attribute.lighting_mode, "Activity Lighting Mode", None, None)
    ],
    Capability.air_conditioner_mode: [
        Map(Attribute.air_conditioner_mode, "Air Conditioner Mode", None, None)
    ],
    Capability.air_quality_sensor: [
        Map(Attribute.air_quality, "Air Quality", "CAQI", None)
    ],
    Capability.alarm: [Map(Attribute.alarm, "Alarm", None, None)],
    Capability.audio_volume: [Map(Attribute.volume, "Volume", PERCENTAGE, None)],
    Capability.battery: [
        Map(Attribute.battery, "Battery", PERCENTAGE, DEVICE_CLASS_BATTERY)
    ],
    Capability.body_mass_index_measurement: [
        Map(
            Attribute.bmi_measurement,
            "Body Mass Index",
            f"{MASS_KILOGRAMS}/{AREA_SQUARE_METERS}",
            None,
        )
    ],
    Capability.body_weight_measurement: [
        Map(Attribute.body_weight_measurement, "Body Weight", MASS_KILOGRAMS, None)
    ],
    Capability.carbon_dioxide_measurement: [
        Map(
            Attribute.carbon_dioxide,
            "Carbon Dioxide Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            None,
        )
    ],
    Capability.carbon_monoxide_detector: [
        Map(Attribute.carbon_monoxide, "Carbon Monoxide Detector", None, None)
    ],
    Capability.carbon_monoxide_measurement: [
        Map(
            Attribute.carbon_monoxide_level,
            "Carbon Monoxide Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            None,
        )
    ],
    Capability.dishwasher_operating_state: [
        Map(Attribute.machine_state, "Dishwasher Machine State", None, None),
        Map(Attribute.dishwasher_job_state, "Dishwasher Job State", None, None),
        Map(
            Attribute.completion_time,
            "Dishwasher Completion Time",
            None,
            DEVICE_CLASS_TIMESTAMP,
        ),
    ],
    Capability.dryer_mode: [Map(Attribute.dryer_mode, "Dryer Mode", None, None)],
    Capability.dryer_operating_state: [
        Map(Attribute.machine_state, "Dryer Machine State", None, None),
        Map(Attribute.dryer_job_state, "Dryer Job State", None, None),
        Map(
            Attribute.completion_time,
            "Dryer Completion Time",
            None,
            DEVICE_CLASS_TIMESTAMP,
        ),
    ],
    Capability.dust_sensor: [
        Map(Attribute.fine_dust_level, "Fine Dust Level", None, None),
        Map(Attribute.dust_level, "Dust Level", None, None),
    ],
    Capability.energy_meter: [
        Map(Attribute.energy, "Energy Meter", ENERGY_KILO_WATT_HOUR, None)
    ],
    Capability.equivalent_carbon_dioxide_measurement: [
        Map(
            Attribute.equivalent_carbon_dioxide_measurement,
            "Equivalent Carbon Dioxide Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            None,
        )
    ],
    Capability.formaldehyde_measurement: [
        Map(
            Attribute.formaldehyde_level,
            "Formaldehyde Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            None,
        )
    ],
    Capability.gas_meter: [
        Map(Attribute.gas_meter, "Gas Meter", ENERGY_KILO_WATT_HOUR, None),
        Map(Attribute.gas_meter_calorific, "Gas Meter Calorific", None, None),
        Map(Attribute.gas_meter_time, "Gas Meter Time", None, DEVICE_CLASS_TIMESTAMP),
        Map(Attribute.gas_meter_volume, "Gas Meter Volume", VOLUME_CUBIC_METERS, None),
    ],
    Capability.illuminance_measurement: [
        Map(Attribute.illuminance, "Illuminance", LIGHT_LUX, DEVICE_CLASS_ILLUMINANCE)
    ],
    Capability.infrared_level: [
        Map(Attribute.infrared_level, "Infrared Level", PERCENTAGE, None)
    ],
    Capability.media_input_source: [
        Map(Attribute.input_source, "Media Input Source", None, None)
    ],
    Capability.media_playback_repeat: [
        Map(Attribute.playback_repeat_mode, "Media Playback Repeat", None, None)
    ],
    Capability.media_playback_shuffle: [
        Map(Attribute.playback_shuffle, "Media Playback Shuffle", None, None)
    ],
    Capability.media_playback: [
        Map(Attribute.playback_status, "Media Playback Status", None, None)
    ],
    Capability.odor_sensor: [Map(Attribute.odor_level, "Odor Sensor", None, None)],
    Capability.oven_mode: [Map(Attribute.oven_mode, "Oven Mode", None, None)],
    Capability.oven_operating_state: [
        Map(Attribute.machine_state, "Oven Machine State", None, None),
        Map(Attribute.oven_job_state, "Oven Job State", None, None),
        Map(Attribute.completion_time, "Oven Completion Time", None, None),
    ],
    Capability.oven_setpoint: [
        Map(Attribute.oven_setpoint, "Oven Set Point", None, None)
    ],
    Capability.power_consumption_report: [
        Map("start", "Start Time", None, DEVICE_CLASS_TIMESTAMP),
        Map("end", "End Time", None, DEVICE_CLASS_TIMESTAMP),
        Map("energy", "Total Energy", ENERGY_WATT_HOUR, DEVICE_CLASS_ENERGY),
        Map("power", "Instantaneous Power", POWER_WATT, DEVICE_CLASS_POWER),
        Map("deltaEnergy", "Load Energy", ENERGY_WATT_HOUR, DEVICE_CLASS_ENERGY),
        Map("powerEnergy", "Power Watt-hours", ENERGY_WATT_HOUR, DEVICE_CLASS_ENERGY),
        Map("energySaved", "Energy Saved", ENERGY_WATT_HOUR, DEVICE_CLASS_ENERGY),
        Map(
            "persistedEnergy", "Persisted Energy", ENERGY_WATT_HOUR, DEVICE_CLASS_ENERGY
        ),
    ],
    Capability.power_meter: [Map(Attribute.power, "Power Meter", POWER_WATT, None)],
    Capability.power_source: [Map(Attribute.power_source, "Power Source", None, None)],
    Capability.refrigeration_setpoint: [
        Map(
            Attribute.refrigeration_setpoint,
            "Refrigeration Setpoint",
            None,
            DEVICE_CLASS_TEMPERATURE,
        )
    ],
    Capability.relative_humidity_measurement: [
        Map(
            Attribute.humidity,
            "Relative Humidity Measurement",
            PERCENTAGE,
            DEVICE_CLASS_HUMIDITY,
        )
    ],
    Capability.robot_cleaner_cleaning_mode: [
        Map(
            Attribute.robot_cleaner_cleaning_mode,
            "Robot Cleaner Cleaning Mode",
            None,
            None,
        )
    ],
    Capability.robot_cleaner_movement: [
        Map(Attribute.robot_cleaner_movement, "Robot Cleaner Movement", None, None)
    ],
    Capability.robot_cleaner_turbo_mode: [
        Map(Attribute.robot_cleaner_turbo_mode, "Robot Cleaner Turbo Mode", None, None)
    ],
    Capability.signal_strength: [
        Map(Attribute.lqi, "LQI Signal Strength", None, None),
        Map(Attribute.rssi, "RSSI Signal Strength", None, None),
    ],
    Capability.smoke_detector: [Map(Attribute.smoke, "Smoke Detector", None, None)],
    Capability.temperature_measurement: [
        Map(
            Attribute.temperature,
            "Temperature Measurement",
            None,
            DEVICE_CLASS_TEMPERATURE,
        )
    ],
    Capability.thermostat_cooling_setpoint: [
        Map(
            Attribute.cooling_setpoint,
            "Thermostat Cooling Setpoint",
            None,
            DEVICE_CLASS_TEMPERATURE,
        )
    ],
    Capability.thermostat_fan_mode: [
        Map(Attribute.thermostat_fan_mode, "Thermostat Fan Mode", None, None)
    ],
    Capability.thermostat_heating_setpoint: [
        Map(
            Attribute.heating_setpoint,
            "Thermostat Heating Setpoint",
            None,
            DEVICE_CLASS_TEMPERATURE,
        )
    ],
    Capability.thermostat_mode: [
        Map(Attribute.thermostat_mode, "Thermostat Mode", None, None)
    ],
    Capability.thermostat_operating_state: [
        Map(
            Attribute.thermostat_operating_state,
            "Thermostat Operating State",
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
        )
    ],
    Capability.three_axis: [],
    Capability.tv_channel: [
        Map(Attribute.tv_channel, "Tv Channel", None, None),
        Map(Attribute.tv_channel_name, "Tv Channel Name", None, None),
    ],
    Capability.tvoc_measurement: [
        Map(
            Attribute.tvoc_level,
            "Tvoc Measurement",
            CONCENTRATION_PARTS_PER_MILLION,
            None,
        )
    ],
    Capability.ultraviolet_index: [
        Map(Attribute.ultraviolet_index, "Ultraviolet Index", None, None)
    ],
    Capability.voltage_measurement: [
        Map(Attribute.voltage, "Voltage Measurement", VOLT, None)
    ],
    Capability.washer_mode: [Map(Attribute.washer_mode, "Washer Mode", None, None)],
    Capability.washer_operating_state: [
        Map(Attribute.machine_state, "Washer Machine State", None, None),
        Map(Attribute.washer_job_state, "Washer Job State", None, None),
        Map(
            Attribute.completion_time,
            "Washer Completion Time",
            None,
            DEVICE_CLASS_TIMESTAMP,
        ),
    ],
}

UNITS = {
    "C": TEMP_CELSIUS,
    "date": ATTR_DATE,
    "F": TEMP_FAHRENHEIT,
    "W": POWER_WATT,
    "Wh": ENERGY_WATT_HOUR,
}

THREE_AXIS_NAMES = ["X Coordinate", "Y Coordinate", "Z Coordinate"]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add binary sensors for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    sensors = []
    for device in broker.devices.values():
        _LOGGER.debug("Status: %s", device.status.attributes)
        for capability in broker.get_assigned(device.device_id, "sensor"):
            if capability == Capability.power_consumption_report:
                maps = CAPABILITY_TO_SENSORS[capability]
                sensors.extend(
                    [
                        SmartThingsPowerConsumptionReportSensor(
                            device,
                            Attribute.power_consumption,
                            m.attribute,
                            m.name,
                            m.default_unit,
                            m.device_class,
                        )
                        for m in maps
                    ]
                )
            elif capability == Capability.three_axis:
                sensors.extend(
                    [
                        SmartThingsThreeAxisSensor(device, index)
                        for index in range(len(THREE_AXIS_NAMES))
                    ]
                )
            else:
                maps = CAPABILITY_TO_SENSORS[capability]
                sensors.extend(
                    [
                        SmartThingsSensor(
                            device, m.attribute, m.name, m.default_unit, m.device_class
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
        self, device, attribute: str, name: str, default_unit: str, device_class: str
    ):
        """Init the class."""
        super().__init__(device)
        self._attribute = attribute
        self._name = name
        self._device_class = device_class
        self._default_unit = default_unit

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return f"{self._device.label} {self._name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._device.device_id}.{self._attribute}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.status.attributes[self._attribute].value

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self):
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
    def state(self):
        """Return the state of the sensor."""
        three_axis = self._device.status.attributes[Attribute.three_axis].value
        try:
            return three_axis[self._index]
        except (TypeError, IndexError):
            return None


class SmartThingsPowerConsumptionReportSensor(SmartThingsSensor):
    """Define a SmartTHings Power Consumption Report."""

    def __init__(
        self,
        device,
        attribute: str,
        sub_attribute: str,
        name: str,
        default_unit: str,
        device_class: str,
    ):
        """Init the class."""
        super().__init__(device, attribute, name, default_unit, device_class)
        self._sub_attribute = sub_attribute

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._device.device_id}.{self._attribute}.{self._sub_attribute}"

    @property
    def state(self):
        """Return the state of the sensor."""
        powerConsumptionReport = self._device.status.attributes[self._attribute].value
        if powerConsumptionReport is None:
            return None
        return powerConsumptionReport.get(self._sub_attribute)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._default_unit
