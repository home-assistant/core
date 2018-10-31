"""
Support for Xiaomi Mi Flora BLE plant sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.miflora/
"""
import asyncio
from datetime import timedelta
import logging
import voluptuous as vol
import async_timeout

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady
from homeassistant.const import (
    CONF_FORCE_UPDATE, CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_MAC,
    CONF_SCAN_INTERVAL)


REQUIREMENTS = ['miflora==0.4.0']

_LOGGER = logging.getLogger(__name__)

CONF_ADAPTER = 'adapter'
CONF_MEDIAN = 'median'

DEFAULT_ADAPTER = 'hci0'
DEFAULT_FORCE_UPDATE = False
DEFAULT_MEDIAN = 3
DEFAULT_NAME = 'Mi Flora'

SCAN_INTERVAL = timedelta(seconds=1200)

# Sensor types are defined like: Name, units
SENSOR_TYPES = {
    'temperature': ['Temperature', '°C'],
    'light': ['Light intensity', 'lx'],
    'moisture': ['Moisture', '%'],
    'conductivity': ['Conductivity', 'µS/cm'],
    'battery': ['Battery', '%'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MEDIAN, default=DEFAULT_MEDIAN): cv.positive_int,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    vol.Optional(CONF_ADAPTER, default=DEFAULT_ADAPTER): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the MiFlora sensor."""
    from miflora import miflora_poller
    try:
        import bluepy.btle  # noqa: F401 pylint: disable=unused-variable
        from btlewrap import BluepyBackend
        backend = BluepyBackend
    except ImportError:
        from btlewrap import GatttoolBackend
        backend = GatttoolBackend
    _LOGGER.debug('Miflora is using %s backend.', backend.__name__)

    cache = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL).total_seconds()
    poller = miflora_poller.MiFloraPoller(
        config.get(CONF_MAC), cache_timeout=cache,
        adapter=config.get(CONF_ADAPTER), backend=backend)
    force_update = config.get(CONF_FORCE_UPDATE)
    median = config.get(CONF_MEDIAN)

    devs = []

    try:
        with async_timeout.timeout(9):
            await hass.async_add_executor_job(poller.fill_cache)
    except asyncio.TimeoutError:
        _LOGGER.error('Unable to connect to %s', config.get(CONF_MAC))
        raise PlatformNotReady

    for parameter in config[CONF_MONITORED_CONDITIONS]:
        name = SENSOR_TYPES[parameter][0]
        unit = SENSOR_TYPES[parameter][1]

        prefix = config.get(CONF_NAME)
        if prefix:
            name = "{} {}".format(prefix, name)

        devs.append(MiFloraSensor(
            poller, parameter, name, unit, force_update, median))

    async_add_entities(devs, update_before_add=True)


class MiFloraSensor(Entity):
    """Implementing the MiFlora sensor."""

    def __init__(self, poller, parameter, name, unit, force_update, median):
        """Initialize the sensor."""
        self.poller = poller
        self.parameter = parameter
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
    def force_update(self):
        """Force update."""
        return self._force_update

    def update(self):
        """
        Update current conditions.

        This uses a rolling median over 3 values to filter out outliers.
        """
        from btlewrap import BluetoothBackendException
        try:
            _LOGGER.debug("Polling data for %s", self.name)
            data = self.poller.parameter_value(self.parameter)
        except IOError as ioerr:
            _LOGGER.info("Polling error %s", ioerr)
            return
        except BluetoothBackendException as bterror:
            _LOGGER.info("Polling error %s", bterror)
            return

        if data is not None:
            _LOGGER.debug("%s = %s", self.name, data)
            self.data.append(data)
        else:
            _LOGGER.info("Did not receive any data from Mi Flora sensor %s",
                         self.name)
            # Remove old data from median list or set sensor value to None
            # if no data is available anymore
            if self.data:
                self.data = self.data[1:]
            else:
                self._state = None
            return

        _LOGGER.debug("Data collected: %s", self.data)
        if len(self.data) > self.median_count:
            self.data = self.data[1:]

        if len(self.data) == self.median_count:
            median = sorted(self.data)[int((self.median_count - 1) / 2)]
            _LOGGER.debug("Median is: %s", median)
            self._state = median
        elif self._state is None:
            _LOGGER.debug("Set initial state")
            self._state = self.data[0]
        else:
            _LOGGER.debug("Not yet enough data for median calculation")
