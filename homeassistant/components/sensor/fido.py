"""
Support for Fido.

Get data from 'Usage Summary' page:
https://www.fido.ca/pages/#/my-account/wireless

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fido/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD,
    CONF_NAME, CONF_MONITORED_VARIABLES)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyfido==2.1.0']

_LOGGER = logging.getLogger(__name__)

KILOBITS = 'Kb'  # type: str
PRICE = 'CAD'  # type: str
MESSAGES = 'messages'  # type: str
MINUTES = 'minutes'  # type: str

DEFAULT_NAME = 'Fido'

REQUESTS_TIMEOUT = 15
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

SENSOR_TYPES = {
    'fido_dollar': ['Fido dollar', PRICE, 'mdi:square-inc-cash'],
    'balance': ['Balance', PRICE, 'mdi:square-inc-cash'],
    'data_used': ['Data used', KILOBITS, 'mdi:download'],
    'data_limit': ['Data limit', KILOBITS, 'mdi:download'],
    'data_remaining': ['Data remaining', KILOBITS, 'mdi:download'],
    'text_used': ['Text used', MESSAGES, 'mdi:message-text'],
    'text_limit': ['Text limit', MESSAGES, 'mdi:message-text'],
    'text_remaining': ['Text remaining', MESSAGES, 'mdi:message-text'],
    'mms_used': ['MMS used', MESSAGES, 'mdi:message-image'],
    'mms_limit': ['MMS limit', MESSAGES, 'mdi:message-image'],
    'mms_remaining': ['MMS remaining', MESSAGES, 'mdi:message-image'],
    'text_int_used': ['International text used',
                      MESSAGES, 'mdi:message-alert'],
    'text_int_limit': ['International text limit',
                       MESSAGES, 'mdi:message-alart'],
    'text_int_remaining': ['Internaltional remaining',
                           MESSAGES, 'mdi:message-alert'],
    'talk_used': ['Talk used', MINUTES, 'mdi:cellphone'],
    'talk_limit': ['Talk limit', MINUTES, 'mdi:cellphone'],
    'talt_remaining': ['Talk remaining', MINUTES, 'mdi:cellphone'],
    'other_talk_used': ['Other Talk used', MINUTES, 'mdi:cellphone'],
    'other_talk_limit': ['Other Talk limit', MINUTES, 'mdi:cellphone'],
    'other_talk_remaining': ['Other Talk remaining', MINUTES, 'mdi:cellphone'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_VARIABLES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Fido sensor."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    httpsession = hass.helpers.aiohttp_client.async_get_clientsession()
    fido_data = FidoData(username, password, httpsession)
    ret = yield from fido_data.async_update()
    if ret is False:
        return

    name = config.get(CONF_NAME)

    sensors = []
    for number in fido_data.client.get_phone_numbers():
        for variable in config[CONF_MONITORED_VARIABLES]:
            sensors.append(FidoSensor(fido_data, variable, name, number))

    async_add_devices(sensors, True)


class FidoSensor(Entity):
    """Implementation of a Fido sensor."""

    def __init__(self, fido_data, sensor_type, name, number):
        """Initialize the sensor."""
        self.client_name = name
        self._number = number
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.fido_data = fido_data
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {} {}'.format(self.client_name, self._number, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            'number': self._number,
        }

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data from Fido and update the state."""
        yield from self.fido_data.async_update()
        if self.type == 'balance':
            if self.fido_data.data.get(self.type) is not None:
                self._state = round(self.fido_data.data[self.type], 2)
        else:
            if self.fido_data.data.get(self._number, {}).get(self.type) \
                  is not None:
                self._state = self.fido_data.data[self._number][self.type]
                self._state = round(self._state, 2)


class FidoData(object):
    """Get data from Fido."""

    def __init__(self, username, password, httpsession):
        """Initialize the data object."""
        from pyfido import FidoClient
        self.client = FidoClient(username, password,
                                 REQUESTS_TIMEOUT, httpsession)
        self.data = {}

    @asyncio.coroutine
    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def async_update(self):
        """Get the latest data from Fido."""
        from pyfido.client import PyFidoError
        try:
            yield from self.client.fetch_data()
        except PyFidoError as exp:
            _LOGGER.error("Error on receive last Fido data: %s", exp)
            return False
        # Update data
        self.data = self.client.get_data()
        return True
