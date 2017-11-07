"""
Support for information about the Italian train system using ViaggiaTreno API.

For more details about this platform please refer to the documentation at
https://home-assistant.io/components/sensor.viaggiatreno

TODO: Resolve station name to station id using API
TODO: Resolve station name from train id (potential errors warning)
TODO: Entity state should always be numerical (delay)?
"""
import logging
import asyncio
import aiohttp
import async_timeout

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = 'Powered by ViaggiaTreno Data'
VIAGGIATRENO_ENDPOINT = ("http://www.viaggiatreno.it/viaggiatrenonew/"
                         "resteasy/viaggiatreno/andamentoTreno/"
                         "{station_id}/{train_id}")

REQUEST_TIMEOUT = 5  # seconds
ICON = 'mdi:train'
MONITORED_INFO = ['numeroTreno', 'origine',
                  'destinazione', 'categoria',
                  'orarioPartenza', 'orarioArrivo',
                  'subTitle', 'compOrarioPartenzaZeroEffettivo',
                  'compOrarioArrivoZeroEffettivo']

DEFAULT_NAME = 'Train {}'

CONF_TRAIN_ID = 'train_id'
CONF_STATION_ID = 'station_id'
CONF_STATION_NAME = 'station_name'
CONF_NAME = 'train_name'

CANCELLED_STRING = 'Cancelled'
ARRIVED_STRING = 'Arrived'
NO_INFORMATION_STRING = 'No information for this train now'
NOT_DEPARTED_STRING = 'Not departed yet'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TRAIN_ID): cv.string,
    vol.Required(CONF_STATION_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATION_NAME): cv.string,
    })


@asyncio.coroutine
def async_setup_platform(hass, config,
                         add_devices, discovery_info=None):
    """Setup the ViaggiaTreno platform."""
    train_id = config.get(CONF_TRAIN_ID)
    station_id = config.get(CONF_STATION_ID)
    name = config.get(CONF_NAME)
    add_devices([ViaggiaTrenoSensor(hass, train_id, station_id, name)])


@asyncio.coroutine
def async_http_request(hass, uri):
    """Perform actual request."""
    try:
        session = async_get_clientsession(hass)
        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            req = yield from session.get(uri)
        if req.status != 200:
            return {'error': req.status}
        else:
            json_response = yield from req.json()
            return json_response
    except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
        _LOGGER.error("Cannot connect to ViaggiaTreno API endpoint: %s",
                      str(exc))
    except ValueError:
        _LOGGER.error("Received non-JSON data from ViaggiaTreno API endpoint")


def has_departed(data):
    """Check if the train has actually departed."""
    try:
        first_station = data['fermate'][0]
        if not data['oraUltimoRilevamento'] and not first_station['effettiva']:
            return False
    except ValueError:
        _LOGGER.error('Cannot fetch first station: %s',
                      str(data))
    return True


def has_arrived(data):
    """Check if the train has already arrived."""
    last_station = data["fermate"][-1]
    if not last_station["effettiva"]:
        return False
    return True


def is_cancelled(data):
    """Check if the train is cancelled."""
    if data['tipoTreno'] == 'ST' and data['provvedimento'] == 1:
        return True
    return False


class ViaggiaTrenoSensor(Entity):
    """Implementation of a ViaggiaTreno sensor."""

    def __init__(self, hass, train_id, station_id, name):
        """Initialize the sensor."""
        self.hass = hass
        self._state = None
        self._attributes = {}
        self._unit = ''
        self._icon = ICON
        self._station_id = station_id

        self.uri = VIAGGIATRENO_ENDPOINT.format(
            station_id=station_id,
            train_id=train_id)

        if not name:
            self._name = "Train {} from {}".format(train_id, station_id)
        else:
            self._name = name.format(train_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return extra attributes."""
        self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        return self._attributes

    @asyncio.coroutine
    def async_update(self):
        """Update state."""
        uri = self.uri
        res = yield from async_http_request(self.hass, uri)
        if res.get('error', ''):
            if res['error'] == 204:
                self._state = NO_INFORMATION_STRING
                self._unit = ''
            else:
                self._state = 'Error: {}'.format(res['error'])
                self._unit = ''
        else:
            for i in MONITORED_INFO:
                self._attributes[i] = res[i]

            if is_cancelled(res):
                self._state = CANCELLED_STRING
                self._icon = 'mdi:cancel'
                self._unit = ''
            elif not has_departed(res):
                self._state = NOT_DEPARTED_STRING
                self._unit = ''
            elif has_arrived(res):
                self._state = ARRIVED_STRING
                self._unit = ''
            else:
                self._state = res.get('ritardo', '0')
                self._unit = 'min'
