"""
Support for Fronius devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.fronius/
"""
import asyncio
from asyncio import TimeoutError
from datetime import timedelta
import logging
import voluptuous as vol
from aiohttp.client_exceptions import ServerDisconnectedError

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['pyfronius==0.2']

_LOGGER = logging.getLogger(__name__)

CONF_TYPE = 'type'
CONF_DEVICEID = 'device'
CONF_SCOPE = 'scope'

TYPE_INVERTER = 'inverter'
TYPE_STORAGE = 'storage'
TYPE_METER = 'meter'
TYPE_POWER_FLOW = 'power_flow'
SCOPE_DEVICE = 'device'
SCOPE_SYSTEM = 'system'

DEFAULT_SCOPE = SCOPE_DEVICE
DEFAULT_DEVICE = None

SENSOR_TYPES = [TYPE_INVERTER, TYPE_STORAGE, TYPE_METER, TYPE_POWER_FLOW]
SCOPE_TYPES = [SCOPE_DEVICE, SCOPE_SYSTEM]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TYPE): vol.In(SENSOR_TYPES),
    vol.Optional(CONF_SCOPE, default=DEFAULT_SCOPE):
        vol.All(cv.ensure_list, [vol.In(SCOPE_TYPES)]),
    vol.Optional(CONF_DEVICEID): cv.positive_int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up of Fronius platform."""
    import pyfronius

    session = async_get_clientsession(hass)
    fronius = pyfronius.Fronius(session, config[CONF_HOST])

    name = "fronius_{}_{}".format(config[CONF_TYPE], config[CONF_HOST])
    if CONF_DEVICEID in config.keys():
        device = config[CONF_DEVICEID]
        name = name + "_{}".format(device)
    else:
        device = DEFAULT_DEVICE

    sensor = FroniusSensor(
        fronius, name, config[CONF_TYPE], config[CONF_SCOPE], device)

    async_add_devices([sensor])

    @asyncio.coroutine
    def async_fronius(event):
        """Update all the fronius sensors."""
        try:
            yield from sensor.async_update()
        except Exception:
            _LOGGER.error("Update of sensor data failed.")

    interval = config.get(CONF_SCAN_INTERVAL) or timedelta(seconds=10)
    async_track_time_interval(hass, async_fronius, interval)


class FroniusSensor(Entity):
    """The Fronius sensor implementation."""

    def __init__(self, data, name, device_type, scope, device):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._type = device_type
        self._device = device
        self._scope = scope
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the current state."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @asyncio.coroutine
    def async_update(self):
        """Retrieve and update latest state."""
        _LOGGER.debug("Update {}".format(self.name))

        values = {}

        try:
            values = yield from self._update()
        except ServerDisconnectedError:
            _LOGGER.error("Sensor data cannot be updated: connection error.")
        except TimeoutError:
            _LOGGER.error("Sensor data cannot be updated: timeout.")

        _LOGGER.debug(values)

        if values:
            self._state = values['status']['Code']
            self._attributes = self._get_attributes(values)

    @asyncio.coroutine
    def _update(self):
        """Get the values for the current state."""
        if self._type == TYPE_INVERTER:
            if self._scope == SCOPE_SYSTEM:
                return self.data.current_system_inverter_data()
            elif self._scope == SCOPE_DEVICE and self._device:
                return self.data.current_inverter_data(self._device)
            elif self._scope == SCOPE_DEVICE:
                return self.data.current_inverter_data()
        elif self._type == TYPE_STORAGE:
            return self.data.current_storage_data()
        elif self._type == TYPE_METER:
            return self.data.current_meter_data()
        elif self._type == TYPE_POWER_FLOW:
            return self.data.current_power_flow()

    def _get_attributes(self, values):
        """Map the attributes and ensure proper values."""
        attributes = {}
        for key in values:
            if 'value' in values[key] and values[key]['value']:
                attributes[key] = values[key]['value']
            else:
                attributes[key] = 0

        return attributes
