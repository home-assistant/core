"""Support for The Things Network's Data storage integration."""
import asyncio
import logging

import aiohttp
from aiohttp.hdrs import ACCEPT, AUTHORIZATION
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import DATA_TTN, TTN_ACCESS_KEY, TTN_APP_ID, TTN_DATA_STORAGE_URL

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE_ID = 'device_id'
ATTR_RAW = 'raw'
ATTR_TIME = 'time'

DEFAULT_TIMEOUT = 10
DEPENDENCIES = ['thethingsnetwork']

CONF_DEVICE_ID = 'device_id'
CONF_VALUES = 'values'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_VALUES): {cv.string: cv.string},
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up The Things Network Data storage sensors."""
    ttn = hass.data.get(DATA_TTN)
    device_id = config.get(CONF_DEVICE_ID)
    values = config.get(CONF_VALUES)
    app_id = ttn.get(TTN_APP_ID)
    access_key = ttn.get(TTN_ACCESS_KEY)

    ttn_data_storage = TtnDataStorage(
        hass, app_id, device_id, access_key, values)
    success = await ttn_data_storage.async_update()

    if not success:
        return False

    devices = []
    for value, unit_of_measurement in values.items():
        devices.append(TtnDataSensor(
            ttn_data_storage, device_id, value, unit_of_measurement))
    async_add_entities(devices, True)


class TtnDataSensor(Entity):
    """Representation of a The Things Network Data Storage sensor."""

    def __init__(self, ttn_data_storage, device_id, value,
                 unit_of_measurement):
        """Initialize a The Things Network Data Storage sensor."""
        self._ttn_data_storage = ttn_data_storage
        self._state = None
        self._device_id = device_id
        self._unit_of_measurement = unit_of_measurement
        self._value = value
        self._name = '{} {}'.format(self._device_id, self._value)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        if self._ttn_data_storage.data is not None:
            try:
                return round(self._state[self._value], 1)
            except KeyError:
                pass

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._ttn_data_storage.data is not None:
            return {
                ATTR_DEVICE_ID: self._device_id,
                ATTR_RAW: self._state['raw'],
                ATTR_TIME: self._state['time'],
            }

    async def async_update(self):
        """Get the current state."""
        await self._ttn_data_storage.async_update()
        self._state = self._ttn_data_storage.data


class TtnDataStorage:
    """Get the latest data from The Things Network Data Storage."""

    def __init__(self, hass, app_id, device_id, access_key, values):
        """Initialize the data object."""
        self.data = None
        self._hass = hass
        self._app_id = app_id
        self._device_id = device_id
        self._values = values
        self._url = TTN_DATA_STORAGE_URL.format(
            app_id=app_id, endpoint='api/v2/query', device_id=device_id)
        self._headers = {
            ACCEPT: CONTENT_TYPE_JSON,
            AUTHORIZATION: 'key {}'.format(access_key),
        }

    async def async_update(self):
        """Get the current state from The Things Network Data Storage."""
        try:
            session = async_get_clientsession(self._hass)
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                req = await session.get(self._url, headers=self._headers)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while accessing: %s", self._url)
            return False

        status = req.status

        if status == 204:
            _LOGGER.error("The device is not available: %s", self._device_id)
            return False

        if status == 401:
            _LOGGER.error(
                "Not authorized for Application ID: %s", self._app_id)
            return False

        if status == 404:
            _LOGGER.error("Application ID is not available: %s", self._app_id)
            return False

        data = await req.json()
        self.data = data[-1]

        for value in self._values.items():
            if value[0] not in self.data.keys():
                _LOGGER.warning("Value not available: %s", value[0])

        return req
