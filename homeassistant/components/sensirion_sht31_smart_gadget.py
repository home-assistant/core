"""
Support for Sensirion SHT31 Smart-Gadget temperature and humidity sensor.

https://www.sensirion.com/fileadmin/user_upload/customers/sensirion/Dokumente/2_Humidity_Sensors/Sensirion_Humidity_Sensors_SHT3x_Smart-Gadget_User-Guide.pdf
"""

import binascii
import logging
import math
import struct
import threading
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import PRECISION_TENTHS
from homeassistant.const import \
    (TEMP_CELSIUS, CONF_NAME, CONF_MONITORED_CONDITIONS, CONF_MAC)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.temperature import display_temp
from homeassistant.util import Throttle

REQUIREMENTS = ["pygatt==3.2.0"]

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "SHT31 Smart-Gadget"

SENSOR_BATTERY = "battery"
SENSOR_TEMPERATURE = "temperature"
SENSOR_HUMIDITY = "humidity"
SENSOR_TYPES = (SENSOR_BATTERY, SENSOR_TEMPERATURE, SENSOR_HUMIDITY)

UUID = "00002235-b38d-4985-720e-0f993a68ee41"
BATTERY_HANDLE = "0x1D"
HUMIDITY_HANDLE = "0x32"
TEMPERATURE_HANDLE = "0x37"

CONNECT_TIMEOUT = 30

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    mac = config.get(CONF_MAC)
    sensor = BluetoothSHT31SmartGadgetSensor(mac)

    sensor_client = SHT31SmartGadgetClient(sensor)

    sensor_classes = {
        SENSOR_BATTERY: SHT31SmartGadgetSensorBattery,
        SENSOR_TEMPERATURE: SHT31SmartGadgetSensorTemperature,
        SENSOR_HUMIDITY: SHT31SmartGadgetSensorHumidity
    }

    devs = []
    for sensor_type, sensor_class in sensor_classes.items():
        name = "{} {}".format(config.get(CONF_NAME), sensor_type.capitalize())
        devs.append(sensor_class(sensor_client, name))

    add_devices(devs)


class BluetoothSHT31SmartGadgetSensor(object):
    def __init__(self, mac):
        import pygatt

        self.mac = mac
        self.device = None
        self.event = threading.Event()
        self.adapter = pygatt.GATTToolBackend()

    def _connect(self):
        import pygatt
        from pygatt.exceptions import NotConnectedError

        if not self._is_connected():
            self.device = None

            self.adapter.start()

            type = pygatt.BLEAddressType.random

            try:
                self.device = self.adapter.connect(self.mac,
                                                   timeout=CONNECT_TIMEOUT,
                                                   address_type=type)
            except NotConnectedError as ex:
                _LOGGER.error("Failed to connect to SHT31 Smart-Gadget\n"
                              "Exception: %s", str(ex))

    def _is_connected(self):
        from pygatt.exceptions import NotConnectedError

        if self.device is not None:
            try:
                self.device.char_read(UUID, timeout=CONNECT_TIMEOUT)
                return True
            except NotConnectedError:
                return False
        else:
            return False

    def read_values(self):
        self._connect()
        battery = self._read_battery()
        temperature = self._read_temperature()
        humidity = self._read_humidity()
        return battery, temperature, humidity

    def _read_battery(self):
        raw = self.device.char_read_handle(BATTERY_HANDLE)
        return int(binascii.hexlify(raw))

    def _read_temperature(self):
        raw = self.device.char_read_handle(TEMPERATURE_HANDLE)
        return struct.unpack("f", raw)[0]

    def _read_humidity(self):
        raw = self.device.char_read_handle(HUMIDITY_HANDLE)
        return struct.unpack("f", raw)[0]


class SHT31SmartGadgetClient(object):
    """Get the latest data from the SHT31 Smart-Gadget sensor."""

    def __init__(self, sensor):
        """Initialize the sensor."""
        self.sensor = sensor
        self.battery = None
        self.temperature = None
        self.humidity = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the SHT31 Smart-Gadget sensor."""
        battery, temperature, humidity = self.sensor.read_values()

        if isinstance(battery, int) and math.isnan(battery):
            _LOGGER.warning("Bad Battery sample from SHT31 Smart-Gadget")
        else:
            self.battery = battery

        if isinstance(temperature, float) and math.isnan(temperature):
            _LOGGER.warning("Bad Temperature sample from SHT31 Smart-Gadget")
        else:
            self.temperature = temperature

        if isinstance(humidity, float) and math.isnan(humidity):
            _LOGGER.warning("Bad Humidity sample from SHT31 Smart-Gadget")
        else:
            self.humidity = humidity


class SHT31SmartGadgetSensor(Entity):
    """
    An abstract SHT31 Smart-Gadget Sensor,
    can be either battery, temperature or humidity.
    """

    def __init__(self, client, name):
        """Initialize the sensor."""
        self._client = client
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Fetch temperature and humidity from the sensor."""
        self._client.update()


class SHT31SmartGadgetSensorBattery(SHT31SmartGadgetSensor):
    """Representation of a battery sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"

    def update(self):
        """Fetch temperature from the sensor."""
        super().update()
        battery = self._client.battery
        if battery is not None:
            self._state = battery

    @property
    def icon(self):
        return "mdi:battery"


class SHT31SmartGadgetSensorTemperature(SHT31SmartGadgetSensor):
    """Representation of a temperature sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.hass.config.units.temperature_unit

    def update(self):
        """Fetch temperature from the sensor."""
        super().update()
        temp_celsius = self._client.temperature
        if temp_celsius is not None:
            self._state = display_temp(self.hass,
                                       temp_celsius,
                                       TEMP_CELSIUS,
                                       PRECISION_TENTHS)

    @property
    def icon(self):
        return "mdi:thermometer-lines"


class SHT31SmartGadgetSensorHumidity(SHT31SmartGadgetSensor):
    """Representation of a humidity sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"

    def update(self):
        """Fetch humidity from the sensor."""
        super().update()
        humidity = self._client.humidity
        if humidity is not None:
            self._state = round(humidity, 2)

    @property
    def icon(self):
        return "mdi:water-percent"
