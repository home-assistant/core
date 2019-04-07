"""Support for the Netatmo devices."""
import logging
from datetime import timedelta
from urllib.error import HTTPError

import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, CONF_DISCOVERY, CONF_URL,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['pyatmo==1.9']
DEPENDENCIES = ['webhook']

_LOGGER = logging.getLogger(__name__)

DATA_PERSONS = 'netatmo_persons'
DATA_WEBHOOK_URL = 'netatmo_webhook_url'

CONF_SECRET_KEY = 'secret_key'
CONF_WEBHOOKS = 'webhooks'

DOMAIN = 'netatmo'

SERVICE_ADDWEBHOOK = 'addwebhook'
SERVICE_DROPWEBHOOK = 'dropwebhook'

NETATMO_AUTH = None
NETATMO_WEBHOOK_URL = None

DEFAULT_PERSON = 'Unknown'
DEFAULT_DISCOVERY = True
DEFAULT_WEBHOOKS = False

EVENT_PERSON = 'person'
EVENT_MOVEMENT = 'movement'
EVENT_HUMAN = 'human'
EVENT_ANIMAL = 'animal'
EVENT_VEHICLE = 'vehicle'

EVENT_BUS_PERSON = 'netatmo_person'
EVENT_BUS_MOVEMENT = 'netatmo_movement'
EVENT_BUS_HUMAN = 'netatmo_human'
EVENT_BUS_ANIMAL = 'netatmo_animal'
EVENT_BUS_VEHICLE = 'netatmo_vehicle'
EVENT_BUS_OTHER = 'netatmo_other'

ATTR_ID = 'id'
ATTR_PSEUDO = 'pseudo'
ATTR_NAME = 'name'
ATTR_EVENT_TYPE = 'event_type'
ATTR_MESSAGE = 'message'
ATTR_CAMERA_ID = 'camera_id'
ATTR_HOME_NAME = 'home_name'
ATTR_PERSONS = 'persons'
ATTR_IS_KNOWN = 'is_known'
ATTR_FACE_URL = 'face_url'
ATTR_SNAPSHOT_URL = 'snapshot_url'
ATTR_VIGNETTE_URL = 'vignette_url'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
MIN_TIME_BETWEEN_EVENT_UPDATES = timedelta(seconds=10)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SECRET_KEY): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_WEBHOOKS, default=DEFAULT_WEBHOOKS): cv.boolean,
        vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)

SCHEMA_SERVICE_ADDWEBHOOK = vol.Schema({
    vol.Optional(CONF_URL): cv.string,
})

SCHEMA_SERVICE_DROPWEBHOOK = vol.Schema({})


def setup(hass, config):
    """Set up the Netatmo devices."""
    import pyatmo

    global NETATMO_AUTH
    hass.data[DATA_PERSONS] = {}
    try:
        NETATMO_AUTH = pyatmo.ClientAuth(
            config[DOMAIN][CONF_API_KEY], config[DOMAIN][CONF_SECRET_KEY],
            config[DOMAIN][CONF_USERNAME], config[DOMAIN][CONF_PASSWORD],
            'read_station read_camera access_camera '
            'read_thermostat write_thermostat '
            'read_presence access_presence read_homecoach')
    except HTTPError:
        _LOGGER.error("Unable to connect to Netatmo API")
        return False

    if config[DOMAIN][CONF_DISCOVERY]:
        for component in 'camera', 'sensor', 'binary_sensor', 'climate':
            discovery.load_platform(hass, component, DOMAIN, {}, config)

    if config[DOMAIN][CONF_WEBHOOKS]:
        webhook_id = hass.components.webhook.async_generate_id()
        hass.data[
            DATA_WEBHOOK_URL] = hass.components.webhook.async_generate_url(
                webhook_id)
        hass.components.webhook.async_register(
            DOMAIN, 'Netatmo', webhook_id, handle_webhook)
        NETATMO_AUTH.addwebhook(hass.data[DATA_WEBHOOK_URL])
        hass.bus.listen_once(
            EVENT_HOMEASSISTANT_STOP, dropwebhook)

    def _service_addwebhook(service):
        """Service to (re)add webhooks during runtime."""
        url = service.data.get(CONF_URL)
        if url is None:
            url = hass.data[DATA_WEBHOOK_URL]
        _LOGGER.info("Adding webhook for URL: %s", url)
        NETATMO_AUTH.addwebhook(url)

    hass.services.register(
        DOMAIN, SERVICE_ADDWEBHOOK, _service_addwebhook,
        schema=SCHEMA_SERVICE_ADDWEBHOOK)

    def _service_dropwebhook(service):
        """Service to drop webhooks during runtime."""
        _LOGGER.info("Dropping webhook")
        NETATMO_AUTH.dropwebhook()

    hass.services.register(
        DOMAIN, SERVICE_DROPWEBHOOK, _service_dropwebhook,
        schema=SCHEMA_SERVICE_DROPWEBHOOK)

    return True


def dropwebhook(hass):
    """Drop the webhook subscription."""
    NETATMO_AUTH.dropwebhook()


async def handle_webhook(hass, webhook_id, request):
    """Handle webhook callback."""
    try:
        data = await request.json()
    except ValueError:
        return None

    _LOGGER.debug("Got webhook data: %s", data)
    published_data = {
        ATTR_EVENT_TYPE: data.get(ATTR_EVENT_TYPE),
        ATTR_HOME_NAME: data.get(ATTR_HOME_NAME),
        ATTR_CAMERA_ID: data.get(ATTR_CAMERA_ID),
        ATTR_MESSAGE: data.get(ATTR_MESSAGE)
    }
    if data.get(ATTR_EVENT_TYPE) == EVENT_PERSON:
        for person in data[ATTR_PERSONS]:
            published_data[ATTR_ID] = person.get(ATTR_ID)
            published_data[ATTR_NAME] = hass.data[DATA_PERSONS].get(
                published_data[ATTR_ID], DEFAULT_PERSON)
            published_data[ATTR_IS_KNOWN] = person.get(ATTR_IS_KNOWN)
            published_data[ATTR_FACE_URL] = person.get(ATTR_FACE_URL)
            hass.bus.async_fire(EVENT_BUS_PERSON, published_data)
    elif data.get(ATTR_EVENT_TYPE) == EVENT_MOVEMENT:
        published_data[ATTR_VIGNETTE_URL] = data.get(ATTR_VIGNETTE_URL)
        published_data[ATTR_SNAPSHOT_URL] = data.get(ATTR_SNAPSHOT_URL)
        hass.bus.async_fire(EVENT_BUS_MOVEMENT, published_data)
    elif data.get(ATTR_EVENT_TYPE) == EVENT_HUMAN:
        published_data[ATTR_VIGNETTE_URL] = data.get(ATTR_VIGNETTE_URL)
        published_data[ATTR_SNAPSHOT_URL] = data.get(ATTR_SNAPSHOT_URL)
        hass.bus.async_fire(EVENT_BUS_HUMAN, published_data)
    elif data.get(ATTR_EVENT_TYPE) == EVENT_ANIMAL:
        published_data[ATTR_VIGNETTE_URL] = data.get(ATTR_VIGNETTE_URL)
        published_data[ATTR_SNAPSHOT_URL] = data.get(ATTR_SNAPSHOT_URL)
        hass.bus.async_fire(EVENT_BUS_ANIMAL, published_data)
    elif data.get(ATTR_EVENT_TYPE) == EVENT_VEHICLE:
        hass.bus.async_fire(EVENT_BUS_VEHICLE, published_data)
        published_data[ATTR_VIGNETTE_URL] = data.get(ATTR_VIGNETTE_URL)
        published_data[ATTR_SNAPSHOT_URL] = data.get(ATTR_SNAPSHOT_URL)
    else:
        hass.bus.async_fire(EVENT_BUS_OTHER, data)


class CameraData:
    """Get the latest data from Netatmo."""

    def __init__(self, hass, auth, home=None):
        """Initialize the data object."""
        self._hass = hass
        self.auth = auth
        self.camera_data = None
        self.camera_names = []
        self.module_names = []
        self.home = home
        self.camera_type = None

    def get_camera_names(self):
        """Return all camera available on the API as a list."""
        self.camera_names = []
        self.update()
        if not self.home:
            for home in self.camera_data.cameras:
                for camera in self.camera_data.cameras[home].values():
                    self.camera_names.append(camera['name'])
        else:
            for camera in self.camera_data.cameras[self.home].values():
                self.camera_names.append(camera['name'])
        return self.camera_names

    def get_module_names(self, camera_name):
        """Return all module available on the API as a list."""
        self.module_names = []
        self.update()
        cam_id = self.camera_data.cameraByName(camera=camera_name,
                                               home=self.home)['id']
        for module in self.camera_data.modules.values():
            if cam_id == module['cam_id']:
                self.module_names.append(module['name'])
        return self.module_names

    def get_camera_type(self, camera=None, home=None, cid=None):
        """Return camera type for a camera, cid has preference over camera."""
        self.camera_type = self.camera_data.cameraType(camera=camera,
                                                       home=home, cid=cid)
        return self.camera_type

    def get_persons(self):
        """Gather person data for webhooks."""
        for person_id, person_data in self.camera_data.persons.items():
            self._hass.data[DATA_PERSONS][person_id] = person_data.get(
                ATTR_PSEUDO)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the Netatmo API to update the data."""
        import pyatmo
        self.camera_data = pyatmo.CameraData(self.auth, size=100)

    @Throttle(MIN_TIME_BETWEEN_EVENT_UPDATES)
    def update_event(self):
        """Call the Netatmo API to update the events."""
        self.camera_data.updateEvent(
            home=self.home, cameratype=self.camera_type)
