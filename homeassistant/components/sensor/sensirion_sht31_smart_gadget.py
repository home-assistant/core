"""
Support for Sensirion SHT31 Smart-Gadget temperature and humidity sensor.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensirion_sht31_smart_gadget/
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

BATTERY_HANDLE = "0x1D"
HUMIDITY_HANDLE = "0x32"
TEMPERATURE_HANDLE = "0x37"

CONNECT_TIMEOUT = 30

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HT31 Smart-Gadget sensor."""

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
    """Logic to get the data from the SHT31 Smart-Gadget sensor."""

    def __init__(self, mac):
        """Initialize the sensor."""

        import pygatt

        self.mac = mac
        self.device = None
        self.event = threading.Event()
        self.adapter = pygatt.GATTToolBackend()

    def _connect(self):
        """Connect to SHT31 Smart-Gadget sensor."""
        import pygatt
        from pygatt.exceptions \
            import (BLEError, NotConnectedError)

        if not self._is_connected():
            self.device = None

            try:
                self.adapter.start()

                ble_type = pygatt.BLEAddressType.random
                self.device = self.adapter.connect(self.mac,
                                                   timeout=CONNECT_TIMEOUT,
                                                   address_type=ble_type)
            except (BLEError, NotConnectedError) as ex:
                _LOGGER.error("Failed to connect to SHT31 Smart-Gadget\n"
                              "Exception: %s", str(ex))

    def _is_connected(self):
        """Check if SHT31 Smart-Gadget sensor is connected."""
        from pygatt.exceptions import NotConnectedError

        if self.device is not None:
            try:
                self.device.discover_characteristics()
                return True
            except NotConnectedError:
                return False
        else:
            return False

    def read_values(self):
        """Read values from SHT31 Smart-Gadget sensor."""
        self._connect()
        battery = self._read_battery()
        temperature = self._read_temperature()
        humidity = self._read_humidity()
        return battery, temperature, humidity

    def _read_battery(self):
        """Read battery value from SHT31 Smart-Gadget sensor."""
        raw = self._read_raw_data(BATTERY_HANDLE)
        if raw is not None:
            return int(binascii.hexlify(raw))
        else:
            return None

    def _read_raw_data(self, handle):
        from pygatt.exceptions \
            import (BLEError, NotConnectedError, NotificationTimeout)

        try:
            return self.device.char_read_handle(handle)
        except (BLEError, NotConnectedError, NotificationTimeout):
            return None

    def _read_temperature(self):
        """Read temperature value from SHT31 Smart-Gadget sensor."""
        raw = self._read_raw_data(TEMPERATURE_HANDLE)
        if raw is not None:
            return struct.unpack("f", raw)[0]
        else:
            return None

    def _read_humidity(self):
        """Read humidity value from SHT31 Smart-Gadget sensor."""
        raw = self._read_raw_data(HUMIDITY_HANDLE)
        if raw is not None:
            return struct.unpack("f", raw)[0]
        else:
            return None


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

        if battery is None and temperature is None and humidity is None:
            self.battery = None
            self.temperature = None
            self.humidity = None
        else:
            if isinstance(battery, int) and math.isnan(battery):
                _LOGGER.warning("Bad Battery sample from "
                                "SHT31 Smart-Gadget")
            else:
                self.battery = battery

            if isinstance(temperature, float) \
                    and math.isnan(temperature):
                _LOGGER.warning("Bad Temperature sample from "
                                "SHT31 Smart-Gadget")
            else:
                self.temperature = temperature

            if isinstance(humidity, float) and math.isnan(humidity):
                _LOGGER.warning("Bad Humidity sample from "
                                "SHT31 Smart-Gadget")
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
        """Fetch battery, temperature and humidity from the sensor."""
        self._client.update()


class SHT31SmartGadgetSensorBattery(SHT31SmartGadgetSensor):
    """Representation of a battery sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"

    def update(self):
        """Fetch battery from the sensor."""
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
