"""Support for Nest Thermostat sensors."""
import logging

from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    STATE_OFF,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UNIT_PERCENTAGE,
)

from . import CONF_SENSORS, DATA_NEST, DATA_NEST_CONFIG, NestSensorDevice

SENSOR_TYPES = ["humidity", "operation_mode", "hvac_state"]

TEMP_SENSOR_TYPES = ["temperature", "target"]

PROTECT_SENSOR_TYPES = [
    "co_status",
    "smoke_status",
    "battery_health",
    # color_status: "gray", "green", "yellow", "red"
    "color_status",
]

STRUCTURE_SENSOR_TYPES = ["eta"]

STATE_HEAT = "heat"
STATE_COOL = "cool"

# security_state is structure level sensor, but only meaningful when
# Nest Cam exist
STRUCTURE_CAMERA_SENSOR_TYPES = ["security_state"]

_VALID_SENSOR_TYPES = (
    SENSOR_TYPES
    + TEMP_SENSOR_TYPES
    + PROTECT_SENSOR_TYPES
    + STRUCTURE_SENSOR_TYPES
    + STRUCTURE_CAMERA_SENSOR_TYPES
)

SENSOR_UNITS = {"humidity": UNIT_PERCENTAGE}

SENSOR_DEVICE_CLASSES = {"humidity": DEVICE_CLASS_HUMIDITY}

VARIABLE_NAME_MAPPING = {"eta": "eta_begin", "operation_mode": "mode"}

VALUE_MAPPING = {
    "hvac_state": {"heating": STATE_HEAT, "cooling": STATE_COOL, "off": STATE_OFF}
}

SENSOR_TYPES_DEPRECATED = ["last_ip", "local_ip", "last_connection", "battery_level"]

DEPRECATED_WEATHER_VARS = [
    "weather_humidity",
    "weather_temperature",
    "weather_condition",
    "wind_speed",
    "wind_direction",
]

_SENSOR_TYPES_DEPRECATED = SENSOR_TYPES_DEPRECATED + DEPRECATED_WEATHER_VARS

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Nest Sensor.

    No longer used.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Nest sensor based on a config entry."""
    nest = hass.data[DATA_NEST]

    discovery_info = hass.data.get(DATA_NEST_CONFIG, {}).get(CONF_SENSORS, {})

    # Add all available sensors if no Nest sensor config is set
    if discovery_info == {}:
        conditions = _VALID_SENSOR_TYPES
    else:
        conditions = discovery_info.get(CONF_MONITORED_CONDITIONS, {})

    for variable in conditions:
        if variable in _SENSOR_TYPES_DEPRECATED:
            if variable in DEPRECATED_WEATHER_VARS:
                wstr = (
                    "Nest no longer provides weather data like %s. See "
                    "https://www.home-assistant.io/integrations/#weather "
                    "for a list of other weather integrations to use." % variable
                )
            else:
                wstr = (
                    variable + " is no a longer supported "
                    "monitored_conditions. See "
                    "https://www.home-assistant.io/integrations/"
                    "binary_sensor.nest/ for valid options."
                )
            _LOGGER.error(wstr)

    def get_sensors():
        """Get the Nest sensors."""
        all_sensors = []
        for structure in nest.structures():
            all_sensors += [
                NestBasicSensor(structure, None, variable)
                for variable in conditions
                if variable in STRUCTURE_SENSOR_TYPES
            ]

        for structure, device in nest.thermostats():
            all_sensors += [
                NestBasicSensor(structure, device, variable)
                for variable in conditions
                if variable in SENSOR_TYPES
            ]
            all_sensors += [
                NestTempSensor(structure, device, variable)
                for variable in conditions
                if variable in TEMP_SENSOR_TYPES
            ]

        for structure, device in nest.smoke_co_alarms():
            all_sensors += [
                NestBasicSensor(structure, device, variable)
                for variable in conditions
                if variable in PROTECT_SENSOR_TYPES
            ]

        structures_has_camera = {}
        for structure, device in nest.cameras():
            structures_has_camera[structure] = True
        for structure in structures_has_camera:
            all_sensors += [
                NestBasicSensor(structure, None, variable)
                for variable in conditions
                if variable in STRUCTURE_CAMERA_SENSOR_TYPES
            ]

        return all_sensors

    async_add_entities(await hass.async_add_job(get_sensors), True)


class NestBasicSensor(NestSensorDevice):
    """Representation a basic Nest sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SENSOR_DEVICE_CLASSES.get(self.variable)

    def update(self):
        """Retrieve latest state."""
        self._unit = SENSOR_UNITS.get(self.variable)

        if self.variable in VARIABLE_NAME_MAPPING:
            self._state = getattr(self.device, VARIABLE_NAME_MAPPING[self.variable])
        elif self.variable in VALUE_MAPPING:
            state = getattr(self.device, self.variable)
            self._state = VALUE_MAPPING[self.variable].get(state, state)
        elif self.variable in PROTECT_SENSOR_TYPES and self.variable != "color_status":
            # keep backward compatibility
            state = getattr(self.device, self.variable)
            self._state = state.capitalize() if state is not None else None
        else:
            self._state = getattr(self.device, self.variable)


class NestTempSensor(NestSensorDevice):
    """Representation of a Nest Temperature sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_TEMPERATURE

    def update(self):
        """Retrieve latest state."""
        if self.device.temperature_scale == "C":
            self._unit = TEMP_CELSIUS
        else:
            self._unit = TEMP_FAHRENHEIT

        temp = getattr(self.device, self.variable)
        if temp is None:
            self._state = None

        if isinstance(temp, tuple):
            low, high = temp
            self._state = "%s-%s" % (int(low), int(high))
        else:
            self._state = round(temp, 1)
