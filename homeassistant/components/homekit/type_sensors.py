"""Class to hold all sensor accessories."""
import logging

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS,
    ATTR_DEVICE_CLASS, STATE_ON, STATE_HOME)

from . import TYPES
from .accessories import HomeAccessory, add_preload_service, setup_char
from .const import (
    CATEGORY_SENSOR, SERV_HUMIDITY_SENSOR, SERV_TEMPERATURE_SENSOR,
    CHAR_CURRENT_HUMIDITY, CHAR_CURRENT_TEMPERATURE, PROP_CELSIUS,
    SERV_AIR_QUALITY_SENSOR, CHAR_AIR_QUALITY, CHAR_AIR_PARTICULATE_DENSITY,
    CHAR_CARBON_DIOXIDE_LEVEL, CHAR_CARBON_DIOXIDE_PEAK_LEVEL,
    SERV_LIGHT_SENSOR, CHAR_CURRENT_AMBIENT_LIGHT_LEVEL,
    DEVICE_CLASS_CO2, SERV_CARBON_DIOXIDE_SENSOR, CHAR_CARBON_DIOXIDE_DETECTED,
    DEVICE_CLASS_GAS, SERV_CARBON_MONOXIDE_SENSOR,
    CHAR_CARBON_MONOXIDE_DETECTED,
    DEVICE_CLASS_MOISTURE, SERV_LEAK_SENSOR, CHAR_LEAK_DETECTED,
    DEVICE_CLASS_MOTION, SERV_MOTION_SENSOR, CHAR_MOTION_DETECTED,
    DEVICE_CLASS_OCCUPANCY, SERV_OCCUPANCY_SENSOR, CHAR_OCCUPANCY_DETECTED,
    DEVICE_CLASS_OPENING, SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE,
    DEVICE_CLASS_DOOR, DEVICE_CLASS_GARAGE_DOOR, DEVICE_CLASS_WINDOW,
    DEVICE_CLASS_SMOKE, SERV_SMOKE_SENSOR, CHAR_SMOKE_DETECTED)
from .util import (
    convert_to_float, temperature_to_homekit, density_to_air_quality)

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_SERVICE_MAP = {
    DEVICE_CLASS_CO2: (SERV_CARBON_DIOXIDE_SENSOR,
                       CHAR_CARBON_DIOXIDE_DETECTED),
    DEVICE_CLASS_DOOR: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE),
    DEVICE_CLASS_GARAGE_DOOR: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE),
    DEVICE_CLASS_GAS: (SERV_CARBON_MONOXIDE_SENSOR,
                       CHAR_CARBON_MONOXIDE_DETECTED),
    DEVICE_CLASS_MOISTURE: (SERV_LEAK_SENSOR, CHAR_LEAK_DETECTED),
    DEVICE_CLASS_MOTION: (SERV_MOTION_SENSOR, CHAR_MOTION_DETECTED),
    DEVICE_CLASS_OCCUPANCY: (SERV_OCCUPANCY_SENSOR, CHAR_OCCUPANCY_DETECTED),
    DEVICE_CLASS_OPENING: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE),
    DEVICE_CLASS_SMOKE: (SERV_SMOKE_SENSOR, CHAR_SMOKE_DETECTED),
    DEVICE_CLASS_WINDOW: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE)}


@TYPES.register('TemperatureSensor')
class TemperatureSensor(HomeAccessory):
    """Generate a TemperatureSensor accessory for a temperature sensor.

    Sensor entity must return temperature in °C, °F.
    """

    def __init__(self, *args, config):
        """Initialize a TemperatureSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        serv_temp = add_preload_service(self, SERV_TEMPERATURE_SENSOR)
        self.char_temp = setup_char(
            CHAR_CURRENT_TEMPERATURE, serv_temp, value=0,
            properties=PROP_CELSIUS)
        self.unit = None

    def update_state(self, new_state):
        """Update temperature after state changed."""
        unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS)
        temperature = convert_to_float(new_state.state)
        if temperature:
            temperature = temperature_to_homekit(temperature, unit)
            self.char_temp.set_value(temperature)
            _LOGGER.debug('%s: Current temperature set to %d°C',
                          self.entity_id, temperature)


@TYPES.register('HumiditySensor')
class HumiditySensor(HomeAccessory):
    """Generate a HumiditySensor accessory as humidity sensor."""

    def __init__(self, *args, config):
        """Initialize a HumiditySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        serv_humidity = add_preload_service(self, SERV_HUMIDITY_SENSOR)
        self.char_humidity = setup_char(
            CHAR_CURRENT_HUMIDITY, serv_humidity, value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        humidity = convert_to_float(new_state.state)
        if humidity:
            self.char_humidity.set_value(humidity)
            _LOGGER.debug('%s: Percent set to %d%%',
                          self.entity_id, humidity)


@TYPES.register('AirQualitySensor')
class AirQualitySensor(HomeAccessory):
    """Generate a AirQualitySensor accessory as air quality sensor."""

    def __init__(self, *args, config):
        """Initialize a AirQualitySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

        serv_air_quality = add_preload_service(self, SERV_AIR_QUALITY_SENSOR,
                                               [CHAR_AIR_PARTICULATE_DENSITY])
        self.char_quality = setup_char(
            CHAR_AIR_QUALITY, serv_air_quality, value=0)
        self.char_density = setup_char(
            CHAR_AIR_PARTICULATE_DENSITY, serv_air_quality, value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        density = convert_to_float(new_state.state)
        if density is not None:
            self.char_density.set_value(density)
            self.char_quality.set_value(density_to_air_quality(density))
            _LOGGER.debug('%s: Set to %d', self.entity_id, density)


@TYPES.register('CarbonDioxideSensor')
class CarbonDioxideSensor(HomeAccessory):
    """Generate a CarbonDioxideSensor accessory as CO2 sensor."""

    def __init__(self, *args, config):
        """Initialize a CarbonDioxideSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

        serv_co2 = add_preload_service(self, SERV_CARBON_DIOXIDE_SENSOR, [
            CHAR_CARBON_DIOXIDE_LEVEL, CHAR_CARBON_DIOXIDE_PEAK_LEVEL])
        self.char_co2 = setup_char(
            CHAR_CARBON_DIOXIDE_LEVEL, serv_co2, value=0)
        self.char_peak = setup_char(
            CHAR_CARBON_DIOXIDE_PEAK_LEVEL, serv_co2, value=0)
        self.char_detected = setup_char(
            CHAR_CARBON_DIOXIDE_DETECTED, serv_co2, value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        co2 = convert_to_float(new_state.state)
        if co2 is not None:
            self.char_co2.set_value(co2)
            if co2 > self.char_peak.value:
                self.char_peak.set_value(co2)
            self.char_detected.set_value(co2 > 1000)
            _LOGGER.debug('%s: Set to %d', self.entity_id, co2)


@TYPES.register('LightSensor')
class LightSensor(HomeAccessory):
    """Generate a LightSensor accessory as light sensor."""

    def __init__(self, *args, config):
        """Initialize a LightSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

        serv_light = add_preload_service(self, SERV_LIGHT_SENSOR)
        self.char_light = setup_char(
            CHAR_CURRENT_AMBIENT_LIGHT_LEVEL, serv_light, value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        luminance = convert_to_float(new_state.state)
        if luminance is not None:
            self.char_light.set_value(luminance)
            _LOGGER.debug('%s: Set to %d', self.entity_id, luminance)


@TYPES.register('BinarySensor')
class BinarySensor(HomeAccessory):
    """Generate a BinarySensor accessory as binary sensor."""

    def __init__(self, *args, config):
        """Initialize a BinarySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        device_class = self.hass.states.get(self.entity_id).attributes \
            .get(ATTR_DEVICE_CLASS)
        service_char = BINARY_SENSOR_SERVICE_MAP[device_class] \
            if device_class in BINARY_SENSOR_SERVICE_MAP \
            else BINARY_SENSOR_SERVICE_MAP[DEVICE_CLASS_OCCUPANCY]

        service = add_preload_service(self, service_char[0])
        self.char_detected = setup_char(service_char[1], service, value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        state = new_state.state
        detected = (state == STATE_ON) or (state == STATE_HOME)
        self.char_detected.set_value(detected)
        _LOGGER.debug('%s: Set to %d', self.entity_id, detected)
