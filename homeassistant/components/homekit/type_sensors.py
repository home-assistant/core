"""Class to hold all sensor accessories."""
import logging

from pyhap.const import CATEGORY_SENSOR

from homeassistant.const import (
    ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT, STATE_ON, STATE_HOME,
    TEMP_CELSIUS)

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    CHAR_AIR_PARTICULATE_DENSITY, CHAR_AIR_QUALITY,
    CHAR_CARBON_DIOXIDE_DETECTED, CHAR_CARBON_DIOXIDE_LEVEL,
    CHAR_CARBON_DIOXIDE_PEAK_LEVEL, CHAR_CARBON_MONOXIDE_DETECTED,
    CHAR_CARBON_MONOXIDE_LEVEL, CHAR_CARBON_MONOXIDE_PEAK_LEVEL,
    CHAR_CONTACT_SENSOR_STATE, CHAR_CURRENT_AMBIENT_LIGHT_LEVEL,
    CHAR_CURRENT_HUMIDITY, CHAR_CURRENT_TEMPERATURE, CHAR_LEAK_DETECTED,
    CHAR_MOTION_DETECTED, CHAR_OCCUPANCY_DETECTED, CHAR_SMOKE_DETECTED,
    DEVICE_CLASS_CO2, DEVICE_CLASS_DOOR, DEVICE_CLASS_GARAGE_DOOR,
    DEVICE_CLASS_GAS, DEVICE_CLASS_MOISTURE, DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY, DEVICE_CLASS_OPENING, DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_WINDOW, PROP_CELSIUS, SERV_AIR_QUALITY_SENSOR,
    SERV_CARBON_DIOXIDE_SENSOR, SERV_CARBON_MONOXIDE_SENSOR,
    SERV_CONTACT_SENSOR, SERV_HUMIDITY_SENSOR, SERV_LEAK_SENSOR,
    SERV_LIGHT_SENSOR, SERV_MOTION_SENSOR, SERV_OCCUPANCY_SENSOR,
    SERV_SMOKE_SENSOR, SERV_TEMPERATURE_SENSOR, THRESHOLD_CO, THRESHOLD_CO2)
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

    def __init__(self, *args):
        """Initialize a TemperatureSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        serv_temp = self.add_preload_service(SERV_TEMPERATURE_SENSOR)
        self.char_temp = serv_temp.configure_char(
            CHAR_CURRENT_TEMPERATURE, value=0, properties=PROP_CELSIUS)

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

    def __init__(self, *args):
        """Initialize a HumiditySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        serv_humidity = self.add_preload_service(SERV_HUMIDITY_SENSOR)
        self.char_humidity = serv_humidity.configure_char(
            CHAR_CURRENT_HUMIDITY, value=0)

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

    def __init__(self, *args):
        """Initialize a AirQualitySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

        serv_air_quality = self.add_preload_service(
            SERV_AIR_QUALITY_SENSOR, [CHAR_AIR_PARTICULATE_DENSITY])
        self.char_quality = serv_air_quality.configure_char(
            CHAR_AIR_QUALITY, value=0)
        self.char_density = serv_air_quality.configure_char(
            CHAR_AIR_PARTICULATE_DENSITY, value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        density = convert_to_float(new_state.state)
        if density:
            self.char_density.set_value(density)
            self.char_quality.set_value(density_to_air_quality(density))
            _LOGGER.debug('%s: Set to %d', self.entity_id, density)


@TYPES.register('CarbonMonoxideSensor')
class CarbonMonoxideSensor(HomeAccessory):
    """Generate a CarbonMonoxidSensor accessory as CO sensor."""

    def __init__(self, *args):
        """Initialize a CarbonMonoxideSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

        serv_co = self.add_preload_service(SERV_CARBON_MONOXIDE_SENSOR, [
            CHAR_CARBON_MONOXIDE_LEVEL, CHAR_CARBON_MONOXIDE_PEAK_LEVEL])
        self.char_level = serv_co.configure_char(
            CHAR_CARBON_MONOXIDE_LEVEL, value=0)
        self.char_peak = serv_co.configure_char(
            CHAR_CARBON_MONOXIDE_PEAK_LEVEL, value=0)
        self.char_detected = serv_co.configure_char(
            CHAR_CARBON_MONOXIDE_DETECTED, value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        value = convert_to_float(new_state.state)
        if value:
            self.char_level.set_value(value)
            if value > self.char_peak.value:
                self.char_peak.set_value(value)
            self.char_detected.set_value(value > THRESHOLD_CO)
            _LOGGER.debug('%s: Set to %d', self.entity_id, value)


@TYPES.register('CarbonDioxideSensor')
class CarbonDioxideSensor(HomeAccessory):
    """Generate a CarbonDioxideSensor accessory as CO2 sensor."""

    def __init__(self, *args):
        """Initialize a CarbonDioxideSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

        serv_co2 = self.add_preload_service(SERV_CARBON_DIOXIDE_SENSOR, [
            CHAR_CARBON_DIOXIDE_LEVEL, CHAR_CARBON_DIOXIDE_PEAK_LEVEL])
        self.char_level = serv_co2.configure_char(
            CHAR_CARBON_DIOXIDE_LEVEL, value=0)
        self.char_peak = serv_co2.configure_char(
            CHAR_CARBON_DIOXIDE_PEAK_LEVEL, value=0)
        self.char_detected = serv_co2.configure_char(
            CHAR_CARBON_DIOXIDE_DETECTED, value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        value = convert_to_float(new_state.state)
        if value:
            self.char_level.set_value(value)
            if value > self.char_peak.value:
                self.char_peak.set_value(value)
            self.char_detected.set_value(value > THRESHOLD_CO2)
            _LOGGER.debug('%s: Set to %d', self.entity_id, value)


@TYPES.register('LightSensor')
class LightSensor(HomeAccessory):
    """Generate a LightSensor accessory as light sensor."""

    def __init__(self, *args):
        """Initialize a LightSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

        serv_light = self.add_preload_service(SERV_LIGHT_SENSOR)
        self.char_light = serv_light.configure_char(
            CHAR_CURRENT_AMBIENT_LIGHT_LEVEL, value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        luminance = convert_to_float(new_state.state)
        if luminance:
            self.char_light.set_value(luminance)
            _LOGGER.debug('%s: Set to %d', self.entity_id, luminance)


@TYPES.register('BinarySensor')
class BinarySensor(HomeAccessory):
    """Generate a BinarySensor accessory as binary sensor."""

    def __init__(self, *args):
        """Initialize a BinarySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        device_class = self.hass.states.get(self.entity_id).attributes \
            .get(ATTR_DEVICE_CLASS)
        service_char = BINARY_SENSOR_SERVICE_MAP[device_class] \
            if device_class in BINARY_SENSOR_SERVICE_MAP \
            else BINARY_SENSOR_SERVICE_MAP[DEVICE_CLASS_OCCUPANCY]

        service = self.add_preload_service(service_char[0])
        self.char_detected = service.configure_char(service_char[1], value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        state = new_state.state
        detected = state in (STATE_ON, STATE_HOME)
        self.char_detected.set_value(detected)
        _LOGGER.debug('%s: Set to %d', self.entity_id, detected)
