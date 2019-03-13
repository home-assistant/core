"""Support for sensors through the SmartThings cloud API."""
from collections import namedtuple
from typing import Optional, Sequence

from homeassistant.const import (
    DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_TIMESTAMP, MASS_KILOGRAMS,
    ENERGY_KILO_WATT_HOUR, POWER_WATT, TEMP_CELSIUS, TEMP_FAHRENHEIT)

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

DEPENDENCIES = ['smartthings']

Map = namedtuple("map", "attribute name default_unit device_class")

CAPABILITY_TO_SENSORS = {
    'activityLightingMode': [
        Map('lightingMode', "Activity Lighting Mode", None, None)],
    'airConditionerMode': [
        Map('airConditionerMode', "Air Conditioner Mode", None, None)],
    'airQualitySensor': [
        Map('airQuality', "Air Quality", 'CAQI', None)],
    'alarm': [
        Map('alarm', "Alarm", None, None)],
    'audioVolume': [
        Map('volume', "Volume", "%", None)],
    'battery': [
        Map('battery', "Battery", "%", DEVICE_CLASS_BATTERY)],
    'bodyMassIndexMeasurement': [
        Map('bmiMeasurement', "Body Mass Index", "kg/m^2", None)],
    'bodyWeightMeasurement': [
        Map('bodyWeightMeasurement', "Body Weight", MASS_KILOGRAMS, None)],
    'carbonDioxideMeasurement': [
        Map('carbonDioxide', "Carbon Dioxide Measurement", "ppm", None)],
    'carbonMonoxideDetector': [
        Map('carbonMonoxide', "Carbon Monoxide Detector", None, None)],
    'carbonMonoxideMeasurement': [
        Map('carbonMonoxideLevel', "Carbon Monoxide Measurement", "ppm",
            None)],
    'dishwasherOperatingState': [
        Map('machineState', "Dishwasher Machine State", None, None),
        Map('dishwasherJobState', "Dishwasher Job State", None, None),
        Map('completionTime', "Dishwasher Completion Time", None,
            DEVICE_CLASS_TIMESTAMP)],
    'dryerMode': [
        Map('dryerMode', "Dryer Mode", None, None)],
    'dryerOperatingState': [
        Map('machineState', "Dryer Machine State", None, None),
        Map('dryerJobState', "Dryer Job State", None, None),
        Map('completionTime', "Dryer Completion Time", None,
            DEVICE_CLASS_TIMESTAMP)],
    'dustSensor': [
        Map('fineDustLevel', "Fine Dust Level", None, None),
        Map('dustLevel', "Dust Level", None, None)],
    'energyMeter': [
        Map('energy', "Energy Meter", ENERGY_KILO_WATT_HOUR, None)],
    'equivalentCarbonDioxideMeasurement': [
        Map('equivalentCarbonDioxideMeasurement',
            'Equivalent Carbon Dioxide Measurement', 'ppm', None)],
    'formaldehydeMeasurement': [
        Map('formaldehydeLevel', 'Formaldehyde Measurement', 'ppm', None)],
    'illuminanceMeasurement': [
        Map('illuminance', "Illuminance", 'lux', DEVICE_CLASS_ILLUMINANCE)],
    'infraredLevel': [
        Map('infraredLevel', "Infrared Level", '%', None)],
    'lock': [
        Map('lock', "Lock", None, None)],
    'mediaInputSource': [
        Map('inputSource', "Media Input Source", None, None)],
    'mediaPlaybackRepeat': [
        Map('playbackRepeatMode', "Media Playback Repeat", None, None)],
    'mediaPlaybackShuffle': [
        Map('playbackShuffle', "Media Playback Shuffle", None, None)],
    'mediaPlayback': [
        Map('playbackStatus', "Media Playback Status", None, None)],
    'odorSensor': [
        Map('odorLevel', "Odor Sensor", None, None)],
    'ovenMode': [
        Map('ovenMode', "Oven Mode", None, None)],
    'ovenOperatingState': [
        Map('machineState', "Oven Machine State", None, None),
        Map('ovenJobState', "Oven Job State", None, None),
        Map('completionTime', "Oven Completion Time", None, None)],
    'ovenSetpoint': [
        Map('ovenSetpoint', "Oven Set Point", None, None)],
    'powerMeter': [
        Map('power', "Power Meter", POWER_WATT, None)],
    'powerSource': [
        Map('powerSource', "Power Source", None, None)],
    'refrigerationSetpoint': [
        Map('refrigerationSetpoint', "Refrigeration Setpoint", None,
            DEVICE_CLASS_TEMPERATURE)],
    'relativeHumidityMeasurement': [
        Map('humidity', "Relative Humidity Measurement", '%',
            DEVICE_CLASS_HUMIDITY)],
    'robotCleanerCleaningMode': [
        Map('robotCleanerCleaningMode', "Robot Cleaner Cleaning Mode",
            None, None)],
    'robotCleanerMovement': [
        Map('robotCleanerMovement', "Robot Cleaner Movement", None, None)],
    'robotCleanerTurboMode': [
        Map('robotCleanerTurboMode', "Robot Cleaner Turbo Mode", None, None)],
    'signalStrength': [
        Map('lqi', "LQI Signal Strength", None, None),
        Map('rssi', "RSSI Signal Strength", None, None)],
    'smokeDetector': [
        Map('smoke', "Smoke Detector", None, None)],
    'temperatureMeasurement': [
        Map('temperature', "Temperature Measurement", None,
            DEVICE_CLASS_TEMPERATURE)],
    'thermostatCoolingSetpoint': [
        Map('coolingSetpoint', "Thermostat Cooling Setpoint", None,
            DEVICE_CLASS_TEMPERATURE)],
    'thermostatFanMode': [
        Map('thermostatFanMode', "Thermostat Fan Mode", None, None)],
    'thermostatHeatingSetpoint': [
        Map('heatingSetpoint', "Thermostat Heating Setpoint", None,
            DEVICE_CLASS_TEMPERATURE)],
    'thermostatMode': [
        Map('thermostatMode', "Thermostat Mode", None, None)],
    'thermostatOperatingState': [
        Map('thermostatOperatingState', "Thermostat Operating State",
            None, None)],
    'thermostatSetpoint': [
        Map('thermostatSetpoint', "Thermostat Setpoint", None,
            DEVICE_CLASS_TEMPERATURE)],
    'threeAxis': [
        Map('threeAxis', "Three Axis", None, None)],
    'tvChannel': [
        Map('tvChannel', "Tv Channel", None, None)],
    'tvocMeasurement': [
        Map('tvocLevel', "Tvoc Measurement", 'ppm', None)],
    'ultravioletIndex': [
        Map('ultravioletIndex', "Ultraviolet Index", None, None)],
    'voltageMeasurement': [
        Map('voltage', "Voltage Measurement", 'V', None)],
    'washerMode': [
        Map('washerMode', "Washer Mode", None, None)],
    'washerOperatingState': [
        Map('machineState', "Washer Machine State", None, None),
        Map('washerJobState', "Washer Job State", None, None),
        Map('completionTime', "Washer Completion Time", None,
            DEVICE_CLASS_TIMESTAMP)]
}

UNITS = {
    'C': TEMP_CELSIUS,
    'F': TEMP_FAHRENHEIT
}

THREE_AXIS_NAMES = ['X Coordinate', 'Y Coordinate', 'Z Coordinate']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Platform uses config entry setup."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add binary sensors for a config entry."""
    from pysmartthings import Capability
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    sensors = []
    for device in broker.devices.values():
        for capability in broker.get_assigned(device.device_id, 'sensor'):
            if capability == Capability.three_axis:
                sensors.extend(
                    [SmartThingsThreeAxisSensor(device, index)
                     for index in range(len(THREE_AXIS_NAMES))])
            else:
                maps = CAPABILITY_TO_SENSORS[capability]
                sensors.extend([
                    SmartThingsSensor(
                        device, m.attribute, m.name, m.default_unit,
                        m.device_class)
                    for m in maps])
    async_add_entities(sensors)


def get_capabilities(capabilities: Sequence[str]) -> Optional[Sequence[str]]:
    """Return all capabilities supported if minimum required are present."""
    return [capability for capability in CAPABILITY_TO_SENSORS
            if capability in capabilities]


class SmartThingsSensor(SmartThingsEntity):
    """Define a SmartThings Sensor."""

    def __init__(self, device, attribute: str, name: str,
                 default_unit: str, device_class: str):
        """Init the class."""
        super().__init__(device)
        self._attribute = attribute
        self._name = name
        self._device_class = device_class
        self._default_unit = default_unit

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return '{} {}'.format(self._device.label, self._name)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return '{}.{}'.format(self._device.device_id, self._attribute)

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


class SmartThingsThreeAxisSensor(SmartThingsEntity):
    """Define a SmartThings Three Axis Sensor."""

    def __init__(self, device, index):
        """Init the class."""
        super().__init__(device)
        self._index = index

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return '{} {}'.format(
            self._device.label, THREE_AXIS_NAMES[self._index])

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return '{}.{}'.format(
            self._device.device_id, THREE_AXIS_NAMES[self._index])

    @property
    def state(self):
        """Return the state of the sensor."""
        from pysmartthings import Attribute
        three_axis = self._device.status.attributes[Attribute.three_axis].value
        try:
            return three_axis[self._index]
        except (TypeError, IndexError):
            return None
