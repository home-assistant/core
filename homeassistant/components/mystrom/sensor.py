"""Support for myStrom plug temperature and power sensors."""
import logging

from pymystrom.exceptions import MyStromConnectionError
from pymystrom.switch import MyStromSwitch as _MyStromSwitch
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_SENSORS,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

DEFAULT_NAME = "myStrom Power Sensor"

_LOGGER = logging.getLogger(__name__)

MONITORED_CONDITIONS = {
    "power": ["Power", POWER_WATT, "mdi:power-plug-outline"],
    "temperature": ["Temperature", TEMP_CELSIUS, "mdi:thermometer"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_SENSORS): vol.All(
            cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the myStrom switch/plug integration."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    try:
        plug = _MyStromSwitch(host)
        await plug.get_state()
    except MyStromConnectionError as err:
        _LOGGER.error("No route to myStrom plug: %s", host)
        raise PlatformNotReady() from err

    sensors = [MyStromSensor(plug, name, idx) for idx in config[CONF_SENSORS]]
    async_add_entities(sensors)


class MyStromSensor(Entity):
    """Representation of a myStrom switch sensors."""

    def __init__(self, plug, name, idx):
        """Initialize the myStrom switch/plug."""
        self._name = name + " " + MONITORED_CONDITIONS[idx][0]
        self.plug = plug
        self._available = True
        self.relay = None
        self.unit = MONITORED_CONDITIONS[idx][1]
        self._icon = MONITORED_CONDITIONS[idx][2]

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return a string with the unit of the sensor."""
        return self.unit

    @property
    def state(self):
        """Return sensor values."""
        if self.unit == POWER_WATT:
            """Return the current power consumption in W."""
            return self.plug.consumption
        if self.unit == TEMP_CELSIUS:
            """Return the temperature near the device."""
            return self.plug.temperature

    async def async_update(self):
        """Get the latest data from the device and update the data."""
        try:
            await self.plug.get_state()
            self.relay = self.plug.relay
            self._available = True
        except MyStromConnectionError:
            self._available = False
            _LOGGER.error("No route to myStrom plug")
