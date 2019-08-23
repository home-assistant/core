"""Platform for beewi_smartclim integration."""
import logging

from datetime import datetime, timedelta
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_NAME,
    CONF_MONITORED_CONDITIONS,
    CONF_MAC,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_BATTERY,
)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# Default values
DEFAULT_NAME = "BeeWi SmartClim"

# Sensor config
SENSOR_TYPES = {
    "temperature": [DEVICE_CLASS_TEMPERATURE, "Temperature", TEMP_CELSIUS],
    "humidity": [DEVICE_CLASS_HUMIDITY, "Humidity", "%"],
    "battery": [DEVICE_CLASS_BATTERY, "Battery", "%"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the beewi_smartclim platform."""
    _LOGGER.info("BeeWi SmartClim has been loaded")

    mac = config.get(CONF_MAC)

    poller = BeewiSmartClimPoller(mac)

    sensors = []

    for parameter in config[CONF_MONITORED_CONDITIONS]:
        device = SENSOR_TYPES[parameter][0]
        name = SENSOR_TYPES[parameter][1]
        unit = SENSOR_TYPES[parameter][2]

        prefix = config.get(CONF_NAME)
        if prefix:
            name = "{} {}".format(prefix, name)

        sensors.append(BeewiSmartclimSensor(poller, name, mac, device, unit))

    add_entities(sensors)


class BeewiSmartclimSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, poller, name, mac, device, unit):
        """Initialize the sensor."""
        self._poller = poller
        self._name = name
        self._mac = mac
        self._device = device
        self._unit = unit
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor. Convert Celsius to Farhenheit if needed."""
        if self._device == DEVICE_CLASS_TEMPERATURE and self._unit == TEMP_FAHRENHEIT:
            return (self._state * 1.8) + 32
        return self._state

    @property
    def device_class(self):
        """Device class of this entity."""
        return self._device

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    def update(self):
        """Fetch new state data from the poller."""
        self._state = self._poller.get_value(self._device)


class BeewiSmartClimPoller:
    """This class will interact with the sensor and aggregates all data."""

    def __init__(self, mac):
        """Initialize the Poller."""
        try:
            from btlewrap import BluepyBackend

            backend = BluepyBackend
        except ImportError:
            from btlewrap import GatttoolBackend

            backend = GatttoolBackend

        self._backend = backend
        self._mac = mac
        self._temp = None
        self._humidity = None
        self._battery = None
        self._last_update = None

        _LOGGER.debug("MiTempBtSensorPoller initiated with backend %s", self._backend)

    def get_value(self, device):
        """Return the value from the cached data."""
        if (self._last_update is None) or (
            datetime.now() - timedelta(minutes=3) > self._last_update
        ):
            self.update_data()
        else:
            _LOGGER.debug("Serving data from cache")

        if device == DEVICE_CLASS_TEMPERATURE:
            return self._temp
        if device == DEVICE_CLASS_HUMIDITY:
            return self._humidity
        if device == DEVICE_CLASS_BATTERY:
            return self._battery
        return None

    def update_data(self):
        """Get data from device."""
        from btlewrap.base import BluetoothInterface, BluetoothBackendException

        bt_interface = BluetoothInterface(self._backend, "hci0")

        try:
            with bt_interface.connect(self._mac) as connection:
                raw = connection.read_handle(0x003F)  # pylint: disable=no-member

            if not raw:
                raise BluetoothBackendException("Could not read 0x003f handle")

            raw_bytes = bytearray(raw)

            temp = int.from_bytes(raw_bytes[1:3], "little") / 10.0
            if temp >= 32768:
                temp = temp - 65535

            humidity = int(raw_bytes[4])
            battery = int(raw_bytes[9])

            self._temp = temp
            self._humidity = humidity
            self._battery = battery
            self._last_update = datetime.now()

            _LOGGER.debug("%s: Find temperature with value: %s", self._mac, self._temp)
            _LOGGER.debug("%s: Find humidity with value: %s", self._mac, self._humidity)
            _LOGGER.debug("%s: Find battery with value: %s", self._mac, self._battery)
        except BluetoothBackendException:
            return
