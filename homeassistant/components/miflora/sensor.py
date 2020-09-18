"""Support for Xiaomi Mi Flora BLE plant sensor."""

from datetime import timedelta
import logging

import btlewrap
from btlewrap import BluetoothBackendException
from miflora import miflora_poller  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONDUCTIVITY,
    CONF_FORCE_UPDATE,
    CONF_MAC,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_START,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util
from homeassistant.util.temperature import celsius_to_fahrenheit

try:
    import bluepy.btle  # noqa: F401 pylint: disable=unused-import

    BACKEND = btlewrap.BluepyBackend
except ImportError:
    BACKEND = btlewrap.GatttoolBackend

_LOGGER = logging.getLogger(__name__)

CONF_ADAPTER = "adapter"
CONF_MEDIAN = "median"
CONF_GO_UNAVAILABLE_TIMEOUT = "go_unavailable_timeout"

DEFAULT_ADAPTER = "hci0"
DEFAULT_FORCE_UPDATE = False
DEFAULT_MEDIAN = 3
DEFAULT_NAME = "Mi Flora"
DEFAULT_GO_UNAVAILABLE_TIMEOUT = timedelta(seconds=7200)

SCAN_INTERVAL = timedelta(seconds=1200)

ATTR_LAST_SUCCESSFUL_UPDATE = "last_successful_update"

# Sensor types are defined like: Name, units, icon
SENSOR_TYPES = {
    "temperature": ["Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "light": ["Light intensity", "lx", "mdi:white-balance-sunny"],
    "moisture": ["Moisture", PERCENTAGE, "mdi:water-percent"],
    "conductivity": ["Conductivity", CONDUCTIVITY, "mdi:flash-circle"],
    "battery": ["Battery", PERCENTAGE, "mdi:battery-charging"],
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
        vol.Optional(CONF_ADAPTER, default=DEFAULT_ADAPTER): cv.string,
        vol.Optional(
            CONF_GO_UNAVAILABLE_TIMEOUT, default=DEFAULT_GO_UNAVAILABLE_TIMEOUT
        ): cv.time_period,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the MiFlora sensor."""
    backend = BACKEND
    _LOGGER.debug("Miflora is using %s backend", backend.__name__)

    cache = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL).total_seconds()
    poller = miflora_poller.MiFloraPoller(
        config.get(CONF_MAC),
        cache_timeout=cache,
        adapter=config.get(CONF_ADAPTER),
        backend=backend,
    )
    force_update = config.get(CONF_FORCE_UPDATE)
    median = config.get(CONF_MEDIAN)

    go_unavailable_timeout = config.get(CONF_GO_UNAVAILABLE_TIMEOUT)

    devs = []

    for parameter in config[CONF_MONITORED_CONDITIONS]:
        name = SENSOR_TYPES[parameter][0]
        unit = (
            hass.config.units.temperature_unit
            if parameter == "temperature"
            else SENSOR_TYPES[parameter][1]
        )
        icon = SENSOR_TYPES[parameter][2]

        prefix = config.get(CONF_NAME)
        if prefix:
            name = f"{prefix} {name}"

        devs.append(
            MiFloraSensor(
                poller,
                parameter,
                name,
                unit,
                icon,
                force_update,
                median,
                go_unavailable_timeout,
            )
        )

    async_add_entities(devs)


class MiFloraSensor(Entity):
    """Implementing the MiFlora sensor."""

    def __init__(
        self,
        poller,
        parameter,
        name,
        unit,
        icon,
        force_update,
        median,
        go_unavailable_timeout,
    ):
        """Initialize the sensor."""
        self.poller = poller
        self.parameter = parameter
        self._unit = unit
        self._icon = icon
        self._name = name
        self._state = None
        self.data = []
        self._force_update = force_update
        self.go_unavailable_timeout = go_unavailable_timeout
        self.last_successful_update = dt_util.utc_from_timestamp(0)
        # Median is used to filter out outliers. median of 3 will filter
        # single outliers, while  median of 5 will filter double outliers
        # Use median_count = 1 if no filtering is required.
        self.median_count = median

    async def async_added_to_hass(self):
        """Set initial state."""

        @callback
        def on_startup(_):
            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, on_startup)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if did update since 2h."""
        return self.last_successful_update > (
            dt_util.utcnow() - self.go_unavailable_timeout
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {ATTR_LAST_SUCCESSFUL_UPDATE: self.last_successful_update}
        return attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

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
        except (OSError, BluetoothBackendException) as err:
            _LOGGER.info("Polling error %s: %s", type(err).__name__, err)
            return

        if data is not None:
            _LOGGER.debug("%s = %s", self.name, data)
            if self._unit == TEMP_FAHRENHEIT:
                data = celsius_to_fahrenheit(data)
            self.data.append(data)
            self.last_successful_update = dt_util.utcnow()
        else:
            _LOGGER.info("Did not receive any data from Mi Flora sensor %s", self.name)
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
