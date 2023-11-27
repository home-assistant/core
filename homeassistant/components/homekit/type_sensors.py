"""Class to hold all sensor accessories."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, NamedTuple

from pyhap.const import CATEGORY_SENSOR
from pyhap.service import Service

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_HOME,
    STATE_ON,
    UnitOfTemperature,
)
from homeassistant.core import State, callback

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
    CHAR_NITROGEN_DIOXIDE_DENSITY,
    CHAR_OCCUPANCY_DETECTED,
    CHAR_PM10_DENSITY,
    CHAR_PM25_DENSITY,
    CHAR_SMOKE_DETECTED,
    CHAR_VOC_DENSITY,
    PROP_CELSIUS,
    PROP_MAX_VALUE,
    PROP_MIN_VALUE,
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
    density_to_air_quality_nitrogen_dioxide,
    density_to_air_quality_pm10,
    density_to_air_quality_voc,
    temperature_to_homekit,
)

_LOGGER = logging.getLogger(__name__)


class SI(NamedTuple):
    """Service info."""

    service: str
    char: str
    format: Callable[[bool], int | bool]


BINARY_SENSOR_SERVICE_MAP: dict[str, SI] = {
    BinarySensorDeviceClass.CO: SI(
        SERV_CARBON_MONOXIDE_SENSOR, CHAR_CARBON_MONOXIDE_DETECTED, int
    ),
    BinarySensorDeviceClass.DOOR: SI(
        SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE, int
    ),
    BinarySensorDeviceClass.GARAGE_DOOR: SI(
        SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE, int
    ),
    BinarySensorDeviceClass.GAS: SI(
        SERV_CARBON_MONOXIDE_SENSOR, CHAR_CARBON_MONOXIDE_DETECTED, int
    ),
    BinarySensorDeviceClass.MOISTURE: SI(SERV_LEAK_SENSOR, CHAR_LEAK_DETECTED, int),
    BinarySensorDeviceClass.MOTION: SI(SERV_MOTION_SENSOR, CHAR_MOTION_DETECTED, bool),
    BinarySensorDeviceClass.OCCUPANCY: SI(
        SERV_OCCUPANCY_SENSOR, CHAR_OCCUPANCY_DETECTED, int
    ),
    BinarySensorDeviceClass.OPENING: SI(
        SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE, int
    ),
    BinarySensorDeviceClass.SMOKE: SI(SERV_SMOKE_SENSOR, CHAR_SMOKE_DETECTED, int),
    BinarySensorDeviceClass.WINDOW: SI(
        SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE, int
    ),
}


@TYPES.register("TemperatureSensor")
class TemperatureSensor(HomeAccessory):
    """Generate a TemperatureSensor accessory for a temperature sensor.

    Sensor entity must return temperature in °C, °F.
    """

    def __init__(self, *args: Any) -> None:
        """Initialize a TemperatureSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        assert state
        serv_temp = self.add_preload_service(SERV_TEMPERATURE_SENSOR)
        self.char_temp = serv_temp.configure_char(
            CHAR_CURRENT_TEMPERATURE, value=0, properties=PROP_CELSIUS
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update temperature after state changed."""
        unit = new_state.attributes.get(
            ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature.CELSIUS
        )
        if (temperature := convert_to_float(new_state.state)) is not None:
            temperature = temperature_to_homekit(temperature, unit)
            self.char_temp.set_value(temperature)
            _LOGGER.debug(
                "%s: Current temperature set to %.1f°C", self.entity_id, temperature
            )


@TYPES.register("HumiditySensor")
class HumiditySensor(HomeAccessory):
    """Generate a HumiditySensor accessory as humidity sensor."""

    def __init__(self, *args: Any) -> None:
        """Initialize a HumiditySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        assert state
        serv_humidity = self.add_preload_service(SERV_HUMIDITY_SENSOR)
        self.char_humidity = serv_humidity.configure_char(
            CHAR_CURRENT_HUMIDITY, value=0
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update accessory after state change."""
        if (humidity := convert_to_float(new_state.state)) is not None:
            self.char_humidity.set_value(humidity)
            _LOGGER.debug("%s: Percent set to %d%%", self.entity_id, humidity)


@TYPES.register("AirQualitySensor")
class AirQualitySensor(HomeAccessory):
    """Generate a AirQualitySensor accessory as air quality sensor."""

    def __init__(self, *args: Any) -> None:
        """Initialize a AirQualitySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        assert state
        self.create_services()

        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def create_services(self) -> None:
        """Initialize a AirQualitySensor accessory object."""
        serv_air_quality = self.add_preload_service(
            SERV_AIR_QUALITY_SENSOR, [CHAR_AIR_PARTICULATE_DENSITY]
        )
        self.char_quality = serv_air_quality.configure_char(CHAR_AIR_QUALITY, value=0)
        self.char_density = serv_air_quality.configure_char(
            CHAR_AIR_PARTICULATE_DENSITY, value=0
        )

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update accessory after state change."""
        if (density := convert_to_float(new_state.state)) is not None:
            if self.char_density.value != density:
                self.char_density.set_value(density)
                _LOGGER.debug("%s: Set density to %d", self.entity_id, density)
            air_quality = density_to_air_quality(density)
            self.char_quality.set_value(air_quality)
            _LOGGER.debug("%s: Set air_quality to %d", self.entity_id, air_quality)


@TYPES.register("PM10Sensor")
class PM10Sensor(AirQualitySensor):
    """Generate a PM10Sensor accessory as PM 10 sensor."""

    def create_services(self) -> None:
        """Override the init function for PM 10 Sensor."""
        serv_air_quality = self.add_preload_service(
            SERV_AIR_QUALITY_SENSOR, [CHAR_PM10_DENSITY]
        )
        self.char_quality = serv_air_quality.configure_char(CHAR_AIR_QUALITY, value=0)
        self.char_density = serv_air_quality.configure_char(CHAR_PM10_DENSITY, value=0)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update accessory after state change."""
        density = convert_to_float(new_state.state)
        if density is None:
            return
        if self.char_density.value != density:
            self.char_density.set_value(density)
            _LOGGER.debug("%s: Set density to %d", self.entity_id, density)
        air_quality = density_to_air_quality_pm10(density)
        if self.char_quality.value != air_quality:
            self.char_quality.set_value(air_quality)
            _LOGGER.debug("%s: Set air_quality to %d", self.entity_id, air_quality)


@TYPES.register("PM25Sensor")
class PM25Sensor(AirQualitySensor):
    """Generate a PM25Sensor accessory as PM 2.5 sensor."""

    def create_services(self) -> None:
        """Override the init function for PM 2.5 Sensor."""
        serv_air_quality = self.add_preload_service(
            SERV_AIR_QUALITY_SENSOR, [CHAR_PM25_DENSITY]
        )
        self.char_quality = serv_air_quality.configure_char(CHAR_AIR_QUALITY, value=0)
        self.char_density = serv_air_quality.configure_char(CHAR_PM25_DENSITY, value=0)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update accessory after state change."""
        density = convert_to_float(new_state.state)
        if density is None:
            return
        if self.char_density.value != density:
            self.char_density.set_value(density)
            _LOGGER.debug("%s: Set density to %d", self.entity_id, density)
        air_quality = density_to_air_quality(density)
        if self.char_quality.value != air_quality:
            self.char_quality.set_value(air_quality)
            _LOGGER.debug("%s: Set air_quality to %d", self.entity_id, air_quality)


@TYPES.register("NitrogenDioxideSensor")
class NitrogenDioxideSensor(AirQualitySensor):
    """Generate a NitrogenDioxideSensor accessory as NO2 sensor."""

    def create_services(self) -> None:
        """Override the init function for PM 2.5 Sensor."""
        serv_air_quality = self.add_preload_service(
            SERV_AIR_QUALITY_SENSOR, [CHAR_NITROGEN_DIOXIDE_DENSITY]
        )
        self.char_quality = serv_air_quality.configure_char(CHAR_AIR_QUALITY, value=0)
        self.char_density = serv_air_quality.configure_char(
            CHAR_NITROGEN_DIOXIDE_DENSITY, value=0
        )

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update accessory after state change."""
        density = convert_to_float(new_state.state)
        if density is None:
            return
        if self.char_density.value != density:
            self.char_density.set_value(density)
            _LOGGER.debug("%s: Set density to %d", self.entity_id, density)
        air_quality = density_to_air_quality_nitrogen_dioxide(density)
        if self.char_quality.value != air_quality:
            self.char_quality.set_value(air_quality)
            _LOGGER.debug("%s: Set air_quality to %d", self.entity_id, air_quality)


@TYPES.register("VolatileOrganicCompoundsSensor")
class VolatileOrganicCompoundsSensor(AirQualitySensor):
    """Generate a VolatileOrganicCompoundsSensor accessory as VOCs sensor.

    Sensor entity must return VOC in µg/m3.
    """

    def create_services(self) -> None:
        """Override the init function for VOC Sensor."""
        serv_air_quality: Service = self.add_preload_service(
            SERV_AIR_QUALITY_SENSOR, [CHAR_VOC_DENSITY]
        )
        self.char_quality = serv_air_quality.configure_char(CHAR_AIR_QUALITY, value=0)
        self.char_density = serv_air_quality.configure_char(
            CHAR_VOC_DENSITY,
            value=0,
            properties={
                PROP_MIN_VALUE: 0,
                PROP_MAX_VALUE: 5000,
            },
        )

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update accessory after state change."""
        density = convert_to_float(new_state.state)
        if density is None:
            return
        if self.char_density.value != density:
            self.char_density.set_value(density)
            _LOGGER.debug("%s: Set density to %d", self.entity_id, density)
        air_quality = density_to_air_quality_voc(density)
        if self.char_quality.value != air_quality:
            self.char_quality.set_value(air_quality)
            _LOGGER.debug("%s: Set air_quality to %d", self.entity_id, air_quality)


@TYPES.register("CarbonMonoxideSensor")
class CarbonMonoxideSensor(HomeAccessory):
    """Generate a CarbonMonoxidSensor accessory as CO sensor."""

    def __init__(self, *args: Any) -> None:
        """Initialize a CarbonMonoxideSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        assert state
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
    def async_update_state(self, new_state: State) -> None:
        """Update accessory after state change."""
        if (value := convert_to_float(new_state.state)) is not None:
            self.char_level.set_value(value)
            if value > self.char_peak.value:
                self.char_peak.set_value(value)
            co_detected = value > THRESHOLD_CO
            self.char_detected.set_value(co_detected)
            _LOGGER.debug("%s: Set to %d", self.entity_id, value)


@TYPES.register("CarbonDioxideSensor")
class CarbonDioxideSensor(HomeAccessory):
    """Generate a CarbonDioxideSensor accessory as CO2 sensor."""

    def __init__(self, *args: Any) -> None:
        """Initialize a CarbonDioxideSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        assert state
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
    def async_update_state(self, new_state: State) -> None:
        """Update accessory after state change."""
        if (value := convert_to_float(new_state.state)) is not None:
            self.char_level.set_value(value)
            if value > self.char_peak.value:
                self.char_peak.set_value(value)
            co2_detected = value > THRESHOLD_CO2
            self.char_detected.set_value(co2_detected)
            _LOGGER.debug("%s: Set to %d", self.entity_id, value)


@TYPES.register("LightSensor")
class LightSensor(HomeAccessory):
    """Generate a LightSensor accessory as light sensor."""

    def __init__(self, *args: Any) -> None:
        """Initialize a LightSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        assert state
        serv_light = self.add_preload_service(SERV_LIGHT_SENSOR)
        self.char_light = serv_light.configure_char(
            CHAR_CURRENT_AMBIENT_LIGHT_LEVEL, value=0
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update accessory after state change."""
        if (luminance := convert_to_float(new_state.state)) is not None:
            self.char_light.set_value(luminance)
            _LOGGER.debug("%s: Set to %d", self.entity_id, luminance)


@TYPES.register("BinarySensor")
class BinarySensor(HomeAccessory):
    """Generate a BinarySensor accessory as binary sensor."""

    def __init__(self, *args: Any) -> None:
        """Initialize a BinarySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        state = self.hass.states.get(self.entity_id)
        assert state
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        service_char = (
            BINARY_SENSOR_SERVICE_MAP[device_class]
            if device_class in BINARY_SENSOR_SERVICE_MAP
            else BINARY_SENSOR_SERVICE_MAP[BinarySensorDeviceClass.OCCUPANCY]
        )

        self.format = service_char.format
        service = self.add_preload_service(service_char.service)
        initial_value = False if self.format is bool else 0
        self.char_detected = service.configure_char(
            service_char.char, value=initial_value
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update accessory after state change."""
        state = new_state.state
        detected = self.format(state in (STATE_ON, STATE_HOME))
        self.char_detected.set_value(detected)
        _LOGGER.debug("%s: Set to %d", self.entity_id, detected)
