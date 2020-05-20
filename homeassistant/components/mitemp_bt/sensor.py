"""Support for Xiaomi Mi Temp BLE environmental sensor."""
import logging

import btlewrap
from btlewrap.base import BluetoothBackendException
from mitemp_bt import mitemp_bt_poller
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_FORCE_UPDATE,
    CONF_MAC,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

try:
    import bluepy.btle  # noqa: F401 pylint: disable=unused-import

    BACKEND = btlewrap.BluepyBackend
except ImportError:
    BACKEND = btlewrap.GatttoolBackend

_LOGGER = logging.getLogger(__name__)

CONF_ADAPTER = "adapter"
CONF_CACHE = "cache_value"
CONF_MEDIAN = "median"
CONF_RETRIES = "retries"
CONF_TIMEOUT = "timeout"

DEFAULT_ADAPTER = "hci0"
DEFAULT_UPDATE_INTERVAL = 300
DEFAULT_FORCE_UPDATE = False
DEFAULT_MEDIAN = 3
DEFAULT_NAME = "MiTemp BT"
DEFAULT_RETRIES = 2
DEFAULT_TIMEOUT = 10


# Sensor types are defined like: Name, units
SENSOR_TYPES = {
    "temperature": [DEVICE_CLASS_TEMPERATURE, "Temperature", TEMP_CELSIUS],
    "humidity": [DEVICE_CLASS_HUMIDITY, "Humidity", UNIT_PERCENTAGE],
    "battery": [DEVICE_CLASS_BATTERY, "Battery", UNIT_PERCENTAGE],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MEDIAN, default=DEFAULT_MEDIAN): cv.positive_int,
        vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_RETRIES, default=DEFAULT_RETRIES): cv.positive_int,
        vol.Optional(CONF_CACHE, default=DEFAULT_UPDATE_INTERVAL): cv.positive_int,
        vol.Optional(CONF_ADAPTER, default=DEFAULT_ADAPTER): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the MiTempBt sensor."""
    backend = BACKEND
    _LOGGER.debug("MiTempBt is using %s backend.", backend.__name__)

    cache = config.get(CONF_CACHE)
    poller = mitemp_bt_poller.MiTempBtPoller(
        config.get(CONF_MAC),
        cache_timeout=cache,
        adapter=config.get(CONF_ADAPTER),
        backend=backend,
    )
    force_update = config.get(CONF_FORCE_UPDATE)
    median = config.get(CONF_MEDIAN)
    poller.ble_timeout = config.get(CONF_TIMEOUT)
    poller.retries = config.get(CONF_RETRIES)

    devs = []

    for parameter in config[CONF_MONITORED_CONDITIONS]:
        device = SENSOR_TYPES[parameter][0]
        name = SENSOR_TYPES[parameter][1]
        unit = SENSOR_TYPES[parameter][2]

        prefix = config.get(CONF_NAME)
        if prefix:
            name = f"{prefix} {name}"

        devs.append(
            MiTempBtSensor(poller, parameter, device, name, unit, force_update, median)
        )

    add_entities(devs)


class MiTempBtSensor(Entity):
    """Implementing the MiTempBt sensor."""

    def __init__(self, poller, parameter, device, name, unit, force_update, median):
        """Initialize the sensor."""
        self.poller = poller
        self.parameter = parameter
        self._device = device
        self._unit = unit
        self._name = name
        self._state = None
        self.data = []
        self._force_update = force_update
        # Median is used to filter out outliers. median of 3 will filter
        # single outliers, while  median of 5 will filter double outliers
        # Use median_count = 1 if no filtering is required.
        self.median_count = median

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit

    @property
    def device_class(self):
        """Device class of this entity."""
        return self._device

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    def update(self):
        """
        Update current conditions.

        This uses a rolling median over 3 values to filter out outliers.
        """
        try:
            _LOGGER.debug("Polling data for %s", self.name)
            data = self.poller.parameter_value(self.parameter)
        except OSError as ioerr:
            _LOGGER.warning("Polling error %s", ioerr)
            return
        except BluetoothBackendException as bterror:
            _LOGGER.warning("Polling error %s", bterror)
            return

        if data is not None:
            _LOGGER.debug("%s = %s", self.name, data)
            self.data.append(data)
        else:
            _LOGGER.warning(
                "Did not receive any data from Mi Temp sensor %s", self.name
            )
            # Remove old data from median list or set sensor value to None
            # if no data is available anymore
            if self.data:
                self.data = self.data[1:]
            else:
                self._state = None
            return

        if len(self.data) > self.median_count:
            self.data = self.data[1:]

        if len(self.data) == self.median_count:
            median = sorted(self.data)[int((self.median_count - 1) / 2)]
            _LOGGER.debug("Median is: %s", median)
            self._state = median
        else:
            _LOGGER.debug("Not yet enough data for median calculation")
