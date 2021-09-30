"""Support for CO2 sensor connected to a serial port."""
from __future__ import annotations

from datetime import timedelta
import logging

from pmsensor import co2sensor
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_DEVICE = "serial_device"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

DEFAULT_NAME = "CO2 Sensor"

ATTR_CO2_CONCENTRATION = "co2_concentration"

SENSOR_TEMPERATURE = "temperature"
SENSOR_CO2 = "co2"
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=SENSOR_CO2,
        name="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=DEVICE_CLASS_CO2,
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_SERIAL_DEVICE): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[SENSOR_CO2]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available CO2 sensors."""

    try:
        co2sensor.read_mh_z19(config.get(CONF_SERIAL_DEVICE))
    except OSError as err:
        _LOGGER.error(
            "Could not open serial connection to %s (%s)",
            config.get(CONF_SERIAL_DEVICE),
            err,
        )
        return False

    data = MHZClient(co2sensor, config.get(CONF_SERIAL_DEVICE))
    name = config[CONF_NAME]

    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    entities = [
        MHZ19Sensor(data, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]

    add_entities(entities, True)


class MHZ19Sensor(SensorEntity):
    """Representation of an CO2 sensor."""

    def __init__(self, mhz_client, name, description: SensorEntityDescription):
        """Initialize a new PM sensor."""
        self.entity_description = description
        self._mhz_client = mhz_client
        self._ppm = None
        self._temperature = None

        self._attr_name = f"{name}: {description.name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.entity_description.key == SENSOR_CO2:
            return self._ppm
        return self._temperature

    def update(self):
        """Read from sensor and update the state."""
        self._mhz_client.update()
        data = self._mhz_client.data
        self._temperature = data.get(SENSOR_TEMPERATURE)
        self._ppm = data.get(SENSOR_CO2)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        result = {}
        sensor_type = self.entity_description.key
        if sensor_type == SENSOR_TEMPERATURE and self._ppm is not None:
            result[ATTR_CO2_CONCENTRATION] = self._ppm
        elif sensor_type == SENSOR_CO2 and self._temperature is not None:
            result[ATTR_TEMPERATURE] = self._temperature
        return result


class MHZClient:
    """Get the latest data from the MH-Z sensor."""

    def __init__(self, co2sens, serial):
        """Initialize the sensor."""
        self.co2sensor = co2sens
        self._serial = serial
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data the MH-Z19 sensor."""
        self.data = {}
        try:
            result = self.co2sensor.read_mh_z19_with_temperature(self._serial)
            if result is None:
                return
            co2, temperature = result

        except OSError as err:
            _LOGGER.error(
                "Could not open serial connection to %s (%s)", self._serial, err
            )
            return

        if temperature is not None:
            self.data[SENSOR_TEMPERATURE] = temperature
        if co2 is not None and 0 < co2 <= 5000:
            self.data[SENSOR_CO2] = co2
