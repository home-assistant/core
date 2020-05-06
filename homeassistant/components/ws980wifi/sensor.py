"""Platform for sensor integration."""
import logging
import select
import socket

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_HPA,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

CONF_BUFFER_SIZE: str = "buffer_size"
LENGTH_MILLIMETERS: str = "mm"
ILLUMINANCE: str = "lux"
UV_VALUE: str = "uW/m²"
UV_INDEX: str = "UV Index"
DEGREE: str = "°"

DEFAULT_BUFFER_SIZE = 1024
DEFAULT_NAME = "WS980WiFi"
DEFAULT_TIMEOUT = 10
DEFAULT_PORT = 45000
DEFAULT_SCAN_INTERVAL = 30

ATTRIBUTION = "ELV WiFi-Wetterstation WS980WiFi"

SENSOR_PROPERTIES = {
    "inside_temperature": [
        "inside temperature",
        TEMP_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        "7",
        "2",
        "10",
    ],
    "outside_temperature": [
        "outside temperature",
        TEMP_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        "10",
        "2",
        "10",
    ],
    "dew_point": ["dew point", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE, "13", "2", "10"],
    "apparent_temperature": [
        "apparent temperature",
        TEMP_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        "16",
        "2",
        "10",
    ],
    "heat_index": [
        "heat index",
        TEMP_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        "19",
        "2",
        "10",
    ],
    "inside_humidity": [
        "inside humidity",
        UNIT_PERCENTAGE,
        DEVICE_CLASS_HUMIDITY,
        "22",
        "1",
        "1",
    ],
    "outside_humidity": [
        "outside humidity",
        UNIT_PERCENTAGE,
        DEVICE_CLASS_HUMIDITY,
        "24",
        "2",
        "1",
    ],
    "pressure_absolute": [
        "pressure absolute",
        PRESSURE_HPA,
        DEVICE_CLASS_PRESSURE,
        "26",
        "2",
        "10",
    ],
    "pressure_relative": [
        "pressure relative",
        PRESSURE_HPA,
        DEVICE_CLASS_PRESSURE,
        "29",
        "2",
        "10",
    ],
    "wind_direction": ["wind direction", DEGREE, None, "32", "2", "1"],
    "wind_speed": ["wind speed", SPEED_METERS_PER_SECOND, None, "35", "2", "10"],
    "gust": ["gust", SPEED_METERS_PER_SECOND, None, "38", "2", "10"],
    "rain": ["rain", LENGTH_MILLIMETERS, None, "41", "4", "10"],
    "rain_day": ["rain day", LENGTH_MILLIMETERS, None, "46", "4", "10"],
    "rain_week": ["rain week", LENGTH_MILLIMETERS, None, "51", "4", "10"],
    "rain_month": ["rain month", LENGTH_MILLIMETERS, None, "56", "4", "10"],
    "rain_year": ["rain year", LENGTH_MILLIMETERS, None, "61", "4", "10"],
    "rain_total": ["rain total", LENGTH_MILLIMETERS, None, "66", "4", "10"],
    "light": ["light", ILLUMINANCE, None, "71", "4", "10"],
    "uv_value": ["uv value", UV_VALUE, None, "76", "2", "10"],
    "uv_index": ["uv index", UV_INDEX, None, "79", "1", "1"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=["inside_temperature"]
        ): vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_PROPERTIES)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    name = config.get(CONF_NAME)

    sensors = []
    for sensor_property in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(WeatherSensor(name, SENSOR_PROPERTIES[sensor_property]))

    weather = WeatherData(hass, sensors, config)
    await weather.fetching_data()
    async_add_entities(sensors)


class WeatherSensor(Entity):
    """Sensor class for all sensor type of this weatherstation."""

    def __init__(self, name, sensor_property):
        """Initialize the sensor."""
        self.client_name = name
        self._state = None
        self._name = sensor_property[0]
        self._unit_of_measurement = sensor_property[1]
        self._device_class = sensor_property[2]
        self._hex_index = int(sensor_property[3])
        self._hex_length = int(sensor_property[4])
        self._decimal_place = int(sensor_property[5])

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class of this entity, if any."""
        return self._device_class

    @property
    def hex_index(self):
        """Return the hex index."""
        return self._hex_index

    @property
    def hex_length(self):
        """Return the hex length."""
        return self._hex_length

    @property
    def decimal_place(self):
        """Return the decimal."""
        return self._decimal_place


class WeatherData(Entity):
    """Get the latest data and updates the states."""

    def __init__(self, hass, sensors, config):
        """Initialize the data object."""
        self.hass = hass
        self.sensors = sensors
        self._config = {
            CONF_HOST: config.get(CONF_HOST),
            CONF_PORT: config.get(CONF_PORT),
            CONF_TIMEOUT: config.get(CONF_TIMEOUT),
            CONF_PAYLOAD: b"\xff\xff\x0b\x00\x06\x04\x04\x19",
            CONF_BUFFER_SIZE: DEFAULT_BUFFER_SIZE,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        }

    async def fetching_data(self, *_):
        """Get the data from weather station."""
        _LOGGER.debug("Updating sensor values from weather station")

        def try_again():
            """Retry in few seconds."""
            seconds = self._config[CONF_SCAN_INTERVAL] * 2
            _LOGGER.error("Retrying in %i seconds", seconds)
            async_call_later(self.hass, seconds, self.fetching_data)

        data = None

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(self._config[CONF_TIMEOUT])
            try:
                sock.connect((self._config[CONF_HOST], self._config[CONF_PORT]))
            except OSError as err:
                _LOGGER.error(
                    "Unable to connect to %s on port %s: %s",
                    self._config[CONF_HOST],
                    self._config[CONF_PORT],
                    err,
                )
                try_again()
                return

            try:
                sock.send(self._config[CONF_PAYLOAD])
            except OSError as err:
                _LOGGER.error(
                    "Unable to send to %s on port %s: %s",
                    self._config[CONF_HOST],
                    self._config[CONF_PORT],
                    err,
                )
                try_again()
                return

            try:
                readable, _, _ = select.select(
                    [sock], [], [], self._config[CONF_TIMEOUT]
                )
                if not readable:
                    _LOGGER.warning(
                        "Timeout (%s second(s)) waiting for a response after "
                        "sending to %s on port %s.",
                        self._config[CONF_TIMEOUT],
                        self._config[CONF_HOST],
                        self._config[CONF_PORT],
                    )
                    try_again()
                    return
            except (UnboundLocalError, TypeError) as err:
                _LOGGER.error("%s", err)
                try_again()
                return

            data = sock.recv(self._config[CONF_BUFFER_SIZE])
            sock.close()
            await self.updating_sensors(data.hex() if data else None)
            async_call_later(
                self.hass, self._config[CONF_SCAN_INTERVAL], self.fetching_data
            )

    async def updating_sensors(self, data):
        """Update all registered sensors."""
        if data.startswith("ffff0b005004"):
            new_state = None
            try:
                for sensor in self.sensors:
                    if data is not None:
                        new_state = data[
                            sensor.hex_index * 2 : sensor.hex_index * 2
                            + sensor.hex_length * 2
                        ]
                        if new_state is not None:
                            if new_state in (
                                "7fff",
                                "ff08",
                                "ff",
                                "0fff",
                                "ffff",
                                "00000000",
                                "00ffffff",
                            ):
                                new_state = None
                            else:
                                new_state = (
                                    float(int(new_state, 16)) / sensor.decimal_place
                                )
                    if new_state != sensor.state:
                        sensor._state = new_state
                        if sensor.hass:
                            _LOGGER.debug("refresh {sensor._name} to {sensor._state}")
                            sensor.async_write_ha_state()
            except (ValueError, TypeError) as err:
                _LOGGER.error(
                    "Unable to update sensor values: %s (%s, %s)", err, data, new_state
                )
