"""Class to hold all sensor accessories."""
import logging

from pyhap.const import CATEGORY_SENSOR

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    STATE_HOME,
    STATE_ON,
    TEMP_CELSIUS,
)
from homeassistant.core import callback

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_AIR_PARTICULATE_DENSITY,
    CHAR_AIR_QUALITY,
    CHAR_CARBON_DIOXIDE_DETECTED,
    CHAR_CARBON_DIOXIDE_LEVEL,
    CHAR_CARBON_DIOXIDE_PEAK_LEVEL,
    CHAR_CARBON_MONOXIDE_DETECTED,
    CHAR_CARBON_MONOXIDE_LEVEL,
    CHAR_CARBON_MONOXIDE_PEAK_LEVEL,
    CHAR_CONTACT_SENSOR_STATE,
    CHAR_CURRENT_AMBIENT_LIGHT_LEVEL,
    CHAR_CURRENT_HUMIDITY,
    CHAR_CURRENT_TEMPERATURE,
    CHAR_LEAK_DETECTED,
    CHAR_MOTION_DETECTED,
    CHAR_OCCUPANCY_DETECTED,
    CHAR_PM10_DENSITY,
    CHAR_PM25_DENSITY,
    CHAR_SMOKE_DETECTED,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GARAGE_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_WINDOW,
    PROP_CELSIUS,
    SERV_AIR_QUALITY_SENSOR,
    SERV_CARBON_DIOXIDE_SENSOR,
    SERV_CARBON_MONOXIDE_SENSOR,
    SERV_CONTACT_SENSOR,
    SERV_HUMIDITY_SENSOR,
    SERV_LEAK_SENSOR,
    SERV_LIGHT_SENSOR,
    SERV_MOTION_SENSOR,
    SERV_OCCUPANCY_SENSOR,
    SERV_SMOKE_SENSOR,
    SERV_TEMPERATURE_SENSOR,
    THRESHOLD_CO,
    THRESHOLD_CO2,
)
from .util import (
    convert_to_float,
    density_to_air_quality,
    density_to_air_quality_pm10,
    density_to_air_quality_pm25,
    temperature_to_homekit,
)

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_SERVICE_MAP = {
    DEVICE_CLASS_CO: (SERV_CARBON_MONOXIDE_SENSOR, CHAR_CARBON_MONOXIDE_DETECTED, int),
    DEVICE_CLASS_CO2: (SERV_CARBON_DIOXIDE_SENSOR, CHAR_CARBON_DIOXIDE_DETECTED, int),
    DEVICE_CLASS_DOOR: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE, int),
    DEVICE_CLASS_GARAGE_DOOR: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE, int),
    DEVICE_CLASS_GAS: (SERV_CARBON_MONOXIDE_SENSOR, CHAR_CARBON_MONOXIDE_DETECTED, int),
    DEVICE_CLASS_MOISTURE: (SERV_LEAK_SENSOR, CHAR_LEAK_DETECTED, int),
    DEVICE_CLASS_MOTION: (SERV_MOTION_SENSOR, CHAR_MOTION_DETECTED, bool),
    DEVICE_CLASS_OCCUPANCY: (SERV_OCCUPANCY_SENSOR, CHAR_OCCUPANCY_DETECTED, int),
    DEVICE_CLASS_OPENING: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE, int),
    DEVICE_CLASS_SMOKE: (SERV_SMOKE_SENSOR, CHAR_SMOKE_DETECTED, int),
    DEVICE_CLASS_WINDOW: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE, int),
}


@TYPES.register("TemperatureSensor")
class TemperatureSensor(HomeAccessory):
    """Generate a TemperatureSensor accessory for a temperature sensor.

    Sensor entity must return temperature in °C, °F.
    """

    def __init__(self, *args):
        """Initialize a TemperatureSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        serv_temp = self.add_preload_service(SERV_TEMPERATURE_SENSOR)
        self.char_temp = serv_temp.configure_char(
            CHAR_CURRENT_TEMPERATURE, value=0, properties=PROP_CELSIUS
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    @callback
    def async_update_state(self, new_state):
        """Update temperature after state changed."""
        unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS)
        temperature = convert_to_float(new_state.state)
        if temperature:
            temperature = temperature_to_homekit(temperature, unit)
            if self.char_temp.value != temperature:
                self.char_temp.set_value(temperature)
                _LOGGER.debug(
                    "%s: Current temperature set to %.1f°C", self.entity_id, temperature
                )


@TYPES.register("HumiditySensor")
class HumiditySensor(HomeAccessory):
    """Generate a HumiditySensor accessory as humidity sensor."""

    def __init__(self, *args):
        """Initialize a HumiditySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        serv_humidity = self.add_preload_service(SERV_HUMIDITY_SENSOR)
        self.char_humidity = serv_humidity.configure_char(
            CHAR_CURRENT_HUMIDITY, value=0
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    @callback
    def async_update_state(self, new_state):
        """Update accessory after state change."""
        humidity = convert_to_float(new_state.state)
        if humidity and self.char_humidity.value != humidity:
            self.char_humidity.set_value(humidity)
            _LOGGER.debug("%s: Percent set to %d%%", self.entity_id, humidity)


@TYPES.register("AirQualitySensor")
class AirQualitySensor(HomeAccessory):
    """Generate a AirQualitySensor accessory as air quality sensor."""

    def __init__(self, *args):
        """Initialize a AirQualitySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)

        self.init()

        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def init(self):
        """Initialize a AirQualitySensor accessory object."""
        serv_air_quality = self.add_preload_service(
            SERV_AIR_QUALITY_SENSOR, [CHAR_AIR_PARTICULATE_DENSITY]
        )
        self.char_quality = serv_air_quality.configure_char(CHAR_AIR_QUALITY, value=0)
        self.char_density = serv_air_quality.configure_char(
            CHAR_AIR_PARTICULATE_DENSITY, value=0
        )

    @callback
    def async_update_state(self, new_state):
        """Update accessory after state change."""
        density = convert_to_float(new_state.state)
        if density:
            if self.char_density.value != density:
                self.char_density.set_value(density)
                _LOGGER.debug("%s: Set density to %d", self.entity_id, density)
            air_quality = density_to_air_quality(density)
            if self.char_quality.value != air_quality:
                self.char_quality.set_value(air_quality)
                _LOGGER.debug("%s: Set air_quality to %d", self.entity_id, air_quality)


@TYPES.register("AirQualitySensor_PM10")
class AirQualitySensor_PM10(AirQualitySensor):
    """Generate a AirQualitySensor_PM10 accessory as PM 10 sensor."""

    def __init__(self, *args):
        """Initialize a AirQualitySensor accessory object."""
        super().__init__(*args)

    def init(self):
        """Override the init function for PM 10 Sensor."""
        serv_air_quality = self.add_preload_service(
            SERV_AIR_QUALITY_SENSOR, [CHAR_PM10_DENSITY]
        )
        self.char_quality = serv_air_quality.configure_char(CHAR_AIR_QUALITY, value=0)
        self.char_density = serv_air_quality.configure_char(CHAR_PM10_DENSITY, value=0)

    @callback
    def async_update_state(self, new_state):
        """Update accessory after state change."""
        density = convert_to_float(new_state.state)
        if density:
            if self.char_density.value != density:
                self.char_density.set_value(density)
                _LOGGER.debug("%s: Set density to %d", self.entity_id, density)
            air_quality = density_to_air_quality_pm10(density)
            if self.char_quality.value != air_quality:
                self.char_quality.set_value(air_quality)
                _LOGGER.debug("%s: Set air_quality to %d", self.entity_id, air_quality)


@TYPES.register("AirQualitySensor_PM25")
class AirQualitySensor_PM25(AirQualitySensor):
    """Generate a AirQualitySensor_PM25 accessory as PM 2.5 sensor."""

    def __init__(self, *args):
        """Initialize a AirQualitySensor accessory object."""
        super().__init__(*args)

    def init(self):
        """Override the init function for PM 2.5 Sensor."""
        serv_air_quality = self.add_preload_service(
            SERV_AIR_QUALITY_SENSOR, [CHAR_PM25_DENSITY]
        )
        self.char_quality = serv_air_quality.configure_char(CHAR_AIR_QUALITY, value=0)
        self.char_density = serv_air_quality.configure_char(CHAR_PM25_DENSITY, value=0)

    @callback
    def async_update_state(self, new_state):
        """Update accessory after state change."""
        density = convert_to_float(new_state.state)
        if density:
            if self.char_density.value != density:
                self.char_density.set_value(density)
                _LOGGER.debug("%s: Set density to %d", self.entity_id, density)
            air_quality = density_to_air_quality_pm25(density)
            if self.char_quality.value != air_quality:
                self.char_quality.set_value(air_quality)
                _LOGGER.debug("%s: Set air_quality to %d", self.entity_id, air_quality)


@TYPES.register("CarbonMonoxideSensor")
class CarbonMonoxideSensor(HomeAccessory):
    """Generate a CarbonMonoxidSensor accessory as CO sensor."""

    def __init__(self, *args):
        """Initialize a CarbonMonoxideSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        serv_co = self.add_preload_service(
            SERV_CARBON_MONOXIDE_SENSOR,
            [CHAR_CARBON_MONOXIDE_LEVEL, CHAR_CARBON_MONOXIDE_PEAK_LEVEL],
        )
        self.char_level = serv_co.configure_char(CHAR_CARBON_MONOXIDE_LEVEL, value=0)
        self.char_peak = serv_co.configure_char(
            CHAR_CARBON_MONOXIDE_PEAK_LEVEL, value=0
        )
        self.char_detected = serv_co.configure_char(
            CHAR_CARBON_MONOXIDE_DETECTED, value=0
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    @callback
    def async_update_state(self, new_state):
        """Update accessory after state change."""
        value = convert_to_float(new_state.state)
        if value:
            if self.char_level.value != value:
                self.char_level.set_value(value)
            if value > self.char_peak.value:
                self.char_peak.set_value(value)
            co_detected = value > THRESHOLD_CO
            if self.char_detected.value is not co_detected:
                self.char_detected.set_value(co_detected)
                _LOGGER.debug("%s: Set to %d", self.entity_id, value)


@TYPES.register("CarbonDioxideSensor")
class CarbonDioxideSensor(HomeAccessory):
    """Generate a CarbonDioxideSensor accessory as CO2 sensor."""

    def __init__(self, *args):
        """Initialize a CarbonDioxideSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        serv_co2 = self.add_preload_service(
            SERV_CARBON_DIOXIDE_SENSOR,
            [CHAR_CARBON_DIOXIDE_LEVEL, CHAR_CARBON_DIOXIDE_PEAK_LEVEL],
        )
        self.char_level = serv_co2.configure_char(CHAR_CARBON_DIOXIDE_LEVEL, value=0)
        self.char_peak = serv_co2.configure_char(
            CHAR_CARBON_DIOXIDE_PEAK_LEVEL, value=0
        )
        self.char_detected = serv_co2.configure_char(
            CHAR_CARBON_DIOXIDE_DETECTED, value=0
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    @callback
    def async_update_state(self, new_state):
        """Update accessory after state change."""
        value = convert_to_float(new_state.state)
        if value:
            if self.char_level.value != value:
                self.char_level.set_value(value)
            if value > self.char_peak.value:
                self.char_peak.set_value(value)
            co2_detected = value > THRESHOLD_CO2
            if self.char_detected.value is not co2_detected:
                self.char_detected.set_value(co2_detected)
                _LOGGER.debug("%s: Set to %d", self.entity_id, value)


@TYPES.register("LightSensor")
class LightSensor(HomeAccessory):
    """Generate a LightSensor accessory as light sensor."""

    def __init__(self, *args):
        """Initialize a LightSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        serv_light = self.add_preload_service(SERV_LIGHT_SENSOR)
        self.char_light = serv_light.configure_char(
            CHAR_CURRENT_AMBIENT_LIGHT_LEVEL, value=0
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    @callback
    def async_update_state(self, new_state):
        """Update accessory after state change."""
        luminance = convert_to_float(new_state.state)
        if luminance and self.char_light.value != luminance:
            self.char_light.set_value(luminance)
            _LOGGER.debug("%s: Set to %d", self.entity_id, luminance)


@TYPES.register("BinarySensor")
class BinarySensor(HomeAccessory):
    """Generate a BinarySensor accessory as binary sensor."""

    def __init__(self, *args):
        """Initialize a BinarySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        service_char = (
            BINARY_SENSOR_SERVICE_MAP[device_class]
            if device_class in BINARY_SENSOR_SERVICE_MAP
            else BINARY_SENSOR_SERVICE_MAP[DEVICE_CLASS_OCCUPANCY]
        )

        self.format = service_char[2]
        service = self.add_preload_service(service_char[0])
        initial_value = False if self.format is bool else 0
        self.char_detected = service.configure_char(
            service_char[1], value=initial_value
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    @callback
    def async_update_state(self, new_state):
        """Update accessory after state change."""
        state = new_state.state
        detected = self.format(state in (STATE_ON, STATE_HOME))
        if self.char_detected.value != detected:
            self.char_detected.set_value(detected)
            _LOGGER.debug("%s: Set to %d", self.entity_id, detected)
