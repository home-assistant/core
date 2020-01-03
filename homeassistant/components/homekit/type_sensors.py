"""Class to hold all sensor accessories."""
import logging

from pyhap.const import CATEGORY_SENSOR

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_HOME,
    STATE_ON,
    TEMP_CELSIUS,
)

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    ATTR_NITROGEN_DIOXIDE_DENSITY,
    ATTR_PM_2_5_DENSITY,
    ATTR_PM_10_DENSITY,
    ATTR_PM_DENSITY,
    ATTR_PM_SIZE,
    ATTR_VOC_DENSITY,
    CHAR_AIR_PARTICULATE_DENSITY,
    CHAR_AIR_PARTICULATE_SIZE,
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
    CHAR_PM_2_5_DENSITY,
    CHAR_PM_10_DENSITY,
    CHAR_SMOKE_DETECTED,
    CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5,
    CHAR_VOC_DENSITY,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GARAGE_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_PM25,
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
    pm_size_to_homekit,
    temperature_to_homekit,
)

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_SERVICE_MAP = {
    DEVICE_CLASS_CO2: (SERV_CARBON_DIOXIDE_SENSOR, CHAR_CARBON_DIOXIDE_DETECTED),
    DEVICE_CLASS_DOOR: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE),
    DEVICE_CLASS_GARAGE_DOOR: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE),
    DEVICE_CLASS_GAS: (SERV_CARBON_MONOXIDE_SENSOR, CHAR_CARBON_MONOXIDE_DETECTED),
    DEVICE_CLASS_MOISTURE: (SERV_LEAK_SENSOR, CHAR_LEAK_DETECTED),
    DEVICE_CLASS_MOTION: (SERV_MOTION_SENSOR, CHAR_MOTION_DETECTED),
    DEVICE_CLASS_OCCUPANCY: (SERV_OCCUPANCY_SENSOR, CHAR_OCCUPANCY_DETECTED),
    DEVICE_CLASS_OPENING: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE),
    DEVICE_CLASS_SMOKE: (SERV_SMOKE_SENSOR, CHAR_SMOKE_DETECTED),
    DEVICE_CLASS_WINDOW: (SERV_CONTACT_SENSOR, CHAR_CONTACT_SENSOR_STATE),
}


@TYPES.register("TemperatureSensor")
class TemperatureSensor(HomeAccessory):
    """Generate a TemperatureSensor accessory for a temperature sensor.

    Sensor entity must return temperature in °C, °F.
    """

    def __init__(self, *args):
        """Initialize a TemperatureSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        serv_temp = self.add_preload_service(SERV_TEMPERATURE_SENSOR)
        self.char_temp = serv_temp.configure_char(
            CHAR_CURRENT_TEMPERATURE, value=0, properties=PROP_CELSIUS
        )

    def update_state(self, new_state):
        """Update temperature after state changed."""
        unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS)
        temperature = convert_to_float(new_state.state)
        if temperature:
            temperature = temperature_to_homekit(temperature, unit)
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
        serv_humidity = self.add_preload_service(SERV_HUMIDITY_SENSOR)
        self.char_humidity = serv_humidity.configure_char(
            CHAR_CURRENT_HUMIDITY, value=0
        )

    def update_state(self, new_state):
        """Update accessory after state change."""
        humidity = convert_to_float(new_state.state)
        if humidity:
            self.char_humidity.set_value(humidity)
            _LOGGER.debug("%s: Percent set to %d%%", self.entity_id, humidity)


@TYPES.register("AirQualitySensor")
class AirQualitySensor(HomeAccessory):
    """Generate a AirQualitySensor accessory as air quality sensor."""

    def __init__(self, *args):
        """Initialize a AirQualitySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

        # determine the charciteristics of the sensor based on the curent attributes
        chars = []
        current_state = self.hass.states.get(self.entity_id)
        nitrogen_dioxide_density = convert_to_float(
            current_state.attributes.get(ATTR_NITROGEN_DIOXIDE_DENSITY)
        )
        voc_density = convert_to_float(current_state.attributes.get(ATTR_VOC_DENSITY))
        pm_2_5_density = convert_to_float(
            current_state.attributes.get(ATTR_PM_2_5_DENSITY)
        )
        pm_10_density = convert_to_float(
            current_state.attributes.get(ATTR_PM_10_DENSITY)
        )
        pm_density = convert_to_float(current_state.attributes.get(ATTR_PM_DENSITY))
        pm_size = convert_to_float(current_state.attributes.get(ATTR_PM_SIZE))
        device_class = current_state.attributes.get(ATTR_DEVICE_CLASS)

        if nitrogen_dioxide_density is not None:
            chars.append(CHAR_NITROGEN_DIOXIDE_DENSITY)

        if voc_density is not None:
            chars.append(CHAR_VOC_DENSITY)

        if pm_2_5_density is not None:
            chars.append(CHAR_PM_2_5_DENSITY)

        if pm_10_density is not None:
            chars.append(CHAR_PM_10_DENSITY)

        if (
            pm_density is not None
            or device_class == DEVICE_CLASS_PM25
            or DEVICE_CLASS_PM25 in self.entity_id
        ):
            chars.append(CHAR_AIR_PARTICULATE_DENSITY)

        if (
            pm_size is not None
            or device_class == DEVICE_CLASS_PM25
            or DEVICE_CLASS_PM25 in self.entity_id
        ):
            chars.append(CHAR_AIR_PARTICULATE_SIZE)

        _LOGGER.debug("%s: chars: %s", self.entity_id, chars)

        # add the service with the determined characteristics
        serv_air_quality = self.add_preload_service(SERV_AIR_QUALITY_SENSOR, chars)
        _LOGGER.debug("%s, service: %s", self.entity_id, serv_air_quality.to_HAP())

        # configure the determined characteristics
        self.char_air_quality = serv_air_quality.configure_char(
            CHAR_AIR_QUALITY, value=0
        )

        if CHAR_NITROGEN_DIOXIDE_DENSITY in chars:
            self.char_nitrogen_dioxide_density = serv_air_quality.configure_char(
                CHAR_NITROGEN_DIOXIDE_DENSITY, value=0
            )

        if CHAR_VOC_DENSITY in chars:
            self.char_voc_density = serv_air_quality.configure_char(
                CHAR_VOC_DENSITY, value=0
            )

        if CHAR_PM_2_5_DENSITY in chars:
            self.char_pm_2_5_density = serv_air_quality.configure_char(
                CHAR_PM_2_5_DENSITY, value=0
            )

        if CHAR_PM_10_DENSITY in chars:
            self.char_pm_10_density = serv_air_quality.configure_char(
                CHAR_PM_10_DENSITY, value=0
            )

        if CHAR_AIR_PARTICULATE_DENSITY in chars:
            self.char_particulate_density = serv_air_quality.configure_char(
                CHAR_AIR_PARTICULATE_DENSITY, value=0
            )

        if CHAR_AIR_PARTICULATE_SIZE in chars:
            self.char_particulate_size = serv_air_quality.configure_char(
                CHAR_AIR_PARTICULATE_SIZE, value=CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5
            )

    def update_state(self, new_state):
        """Update accessory after state change."""
        nitrogen_dioxide_density = convert_to_float(
            new_state.attributes.get(ATTR_NITROGEN_DIOXIDE_DENSITY)
        )
        voc_density = convert_to_float(new_state.attributes.get(ATTR_VOC_DENSITY))
        pm_2_5_density = convert_to_float(new_state.attributes.get(ATTR_PM_2_5_DENSITY))
        pm_10_density = convert_to_float(new_state.attributes.get(ATTR_PM_10_DENSITY))
        pm_density = convert_to_float(new_state.attributes.get(ATTR_PM_DENSITY))
        pm_size = convert_to_float(new_state.attributes.get(ATTR_PM_SIZE))

        # if device class or entity ID contain DEVICE_CLASS_PM25 then assume state is a PM25 reading
        # else assume that state is a HomeKit Air Qaulity Characteristic Value (https://developer.apple.com/documentation/homekit/hmcharacteristicvalueairquality) and use sensory entity attributes
        device_class = new_state.attributes.get(ATTR_DEVICE_CLASS)
        if (device_class == DEVICE_CLASS_PM25) or (
            DEVICE_CLASS_PM25 in new_state.entity_id
        ):
            pm_density = convert_to_float(new_state.state)
            air_quality = density_to_air_quality(pm_density)

            self.char_air_quality.set_value(air_quality)
            self.char_particulate_density.set_value(pm_density)
            self.char_particulate_size.set_value(CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5)
            _LOGGER.debug(
                "%s: Set %s to %d", self.entity_id, CHAR_AIR_QUALITY, air_quality
            )
            _LOGGER.debug(
                "%s: Set %s to %d",
                self.entity_id,
                CHAR_AIR_PARTICULATE_DENSITY,
                pm_density,
            )
            _LOGGER.debug(
                "%s: Set %s to %d", self.entity_id, CHAR_AIR_PARTICULATE_SIZE, pm_size
            )
        else:
            air_quality = convert_to_float(new_state.state)
            if air_quality is not None:
                self.char_air_quality.set_value(air_quality)
                _LOGGER.debug(
                    "%s: Set %s to %d", self.entity_id, CHAR_AIR_QUALITY, air_quality
                )

            if nitrogen_dioxide_density is not None:
                self.char_nitrogen_dioxide_density.set_value(nitrogen_dioxide_density)
                _LOGGER.debug(
                    "%s: Set %s to %d",
                    self.entity_id,
                    CHAR_NITROGEN_DIOXIDE_DENSITY,
                    nitrogen_dioxide_density,
                )

            if voc_density is not None:
                self.char_voc_density.set_value(voc_density)
                _LOGGER.debug(
                    "%s: Set %s to %d", self.entity_id, CHAR_VOC_DENSITY, voc_density
                )

            if pm_2_5_density is not None:
                self.char_pm_2_5_density.set_value(pm_2_5_density)
                _LOGGER.debug(
                    "%s: Set %s to %d",
                    self.entity_id,
                    CHAR_PM_2_5_DENSITY,
                    pm_2_5_density,
                )

            if pm_10_density is not None:
                self.char_pm_10_density.set_value(pm_10_density)
                _LOGGER.debug(
                    "%s: Set %s to %d",
                    self.entity_id,
                    CHAR_PM_10_DENSITY,
                    pm_10_density,
                )

            if pm_density is not None:
                self.char_particulate_density.set_value(pm_density)
                _LOGGER.debug(
                    "%s: Set %s to %d",
                    self.entity_id,
                    CHAR_AIR_PARTICULATE_DENSITY,
                    pm_density,
                )

            # convert the given PM size to value HomeKit Expects
            # (https://developer.apple.com/documentation/homekit/hmcharacteristicvalueairparticulatesize)
            pm_size_char_value = None
            if pm_size:
                try:
                    pm_size_char_value = pm_size_to_homekit(pm_size)
                except (ValueError):
                    _LOGGER.warning(
                        "%s: Given pm_size is not valid value, ignoring.",
                        self.entity_id,
                    )

            if pm_size_char_value:
                self.char_particulate_size.set_value(pm_size_char_value)
                _LOGGER.debug(
                    "%s: Set %s to %d",
                    self.entity_id,
                    CHAR_AIR_PARTICULATE_SIZE,
                    pm_size_char_value,
                )


@TYPES.register("CarbonMonoxideSensor")
class CarbonMonoxideSensor(HomeAccessory):
    """Generate a CarbonMonoxidSensor accessory as CO sensor."""

    def __init__(self, *args):
        """Initialize a CarbonMonoxideSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

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

    def update_state(self, new_state):
        """Update accessory after state change."""
        value = convert_to_float(new_state.state)
        if value:
            self.char_level.set_value(value)
            if value > self.char_peak.value:
                self.char_peak.set_value(value)
            self.char_detected.set_value(value > THRESHOLD_CO)
            _LOGGER.debug("%s: Set to %d", self.entity_id, value)


@TYPES.register("CarbonDioxideSensor")
class CarbonDioxideSensor(HomeAccessory):
    """Generate a CarbonDioxideSensor accessory as CO2 sensor."""

    def __init__(self, *args):
        """Initialize a CarbonDioxideSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

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

    def update_state(self, new_state):
        """Update accessory after state change."""
        value = convert_to_float(new_state.state)
        if value:
            self.char_level.set_value(value)
            if value > self.char_peak.value:
                self.char_peak.set_value(value)
            self.char_detected.set_value(value > THRESHOLD_CO2)
            _LOGGER.debug("%s: Set to %d", self.entity_id, value)


@TYPES.register("LightSensor")
class LightSensor(HomeAccessory):
    """Generate a LightSensor accessory as light sensor."""

    def __init__(self, *args):
        """Initialize a LightSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)

        serv_light = self.add_preload_service(SERV_LIGHT_SENSOR)
        self.char_light = serv_light.configure_char(
            CHAR_CURRENT_AMBIENT_LIGHT_LEVEL, value=0
        )

    def update_state(self, new_state):
        """Update accessory after state change."""
        luminance = convert_to_float(new_state.state)
        if luminance:
            self.char_light.set_value(luminance)
            _LOGGER.debug("%s: Set to %d", self.entity_id, luminance)


@TYPES.register("BinarySensor")
class BinarySensor(HomeAccessory):
    """Generate a BinarySensor accessory as binary sensor."""

    def __init__(self, *args):
        """Initialize a BinarySensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        device_class = self.hass.states.get(self.entity_id).attributes.get(
            ATTR_DEVICE_CLASS
        )
        service_char = (
            BINARY_SENSOR_SERVICE_MAP[device_class]
            if device_class in BINARY_SENSOR_SERVICE_MAP
            else BINARY_SENSOR_SERVICE_MAP[DEVICE_CLASS_OCCUPANCY]
        )

        service = self.add_preload_service(service_char[0])
        self.char_detected = service.configure_char(service_char[1], value=0)

    def update_state(self, new_state):
        """Update accessory after state change."""
        state = new_state.state
        detected = state in (STATE_ON, STATE_HOME)
        self.char_detected.set_value(detected)
        _LOGGER.debug("%s: Set to %d", self.entity_id, detected)
