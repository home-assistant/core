"""
Support for the Netatmo devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/netatmo/
"""
import logging
import json
from datetime import timedelta
from urllib.error import HTTPError

import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, CONF_DISCOVERY,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['pyatmo==1.8']
DEPENDENCIES = ['webhook']

_LOGGER = logging.getLogger(__name__)

CONF_SECRET_KEY = 'secret_key'
CONF_WEBHOOK_URL = 'webhook_url'

DOMAIN = 'netatmo'

NETATMO_AUTH = None
NETATMO_PERSONS = {}
DEFAULT_PERSON = 'Unknown'
DEFAULT_DISCOVERY = True

EVENT_RECEIVED = 'netatmo_webhook_received'
EVENT_PERSON = 'person'
EVENT_MOVEMENT = 'movement'

ATTR_ID = 'id'
ATTR_PSEUDO = 'pseudo'
ATTR_NAME = 'name'
ATTR_EVENT_TYPE = 'event_type'
ATTR_MESSAGE = 'message'
ATTR_CAMERA_ID = 'camera_id'
ATTR_HOME_NAME = 'home_name'
ATTR_PERSONS = 'persons'
ATTR_IS_KNOWN = 'is_known'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
MIN_TIME_BETWEEN_EVENT_UPDATES = timedelta(seconds=10)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SECRET_KEY): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_WEBHOOK_URL): cv.string,
        vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Netatmo devices."""
    import pyatmo

    global NETATMO_AUTH
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

    if config[DOMAIN][CONF_WEBHOOK_URL]:
        webhook_url = config[DOMAIN].get(CONF_WEBHOOK_URL)
        webhook_id = webhook_url.split('/')[-1]
        hass.components.webhook.async_register(
            DOMAIN, 'Netatmo', webhook_id, handle_webhook)
        NETATMO_AUTH.addwebhook(webhook_url)
        hass.bus.listen_once(
            EVENT_HOMEASSISTANT_STOP, dropwebhook)

    return True


def dropwebhook(hass):
    """Drop the webhook subscription."""
    NETATMO_AUTH.dropwebhook()

async def handle_webhook(hass, webhook_id, request):
    """Handle webhook callback."""
    body = await request.text()
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        return None

    published_data = {}
    if isinstance(data, dict):
        published_data['webhook_id'] = webhook_id
    if data.get(ATTR_EVENT_TYPE) == EVENT_PERSON:
        published_data[ATTR_EVENT_TYPE] = EVENT_PERSON
        published_data[ATTR_HOME_NAME] = data.get(ATTR_HOME_NAME)
        published_data[ATTR_CAMERA_ID] = data.get(ATTR_CAMERA_ID)
        published_data[ATTR_MESSAGE] = data.get(ATTR_MESSAGE)
        for person in data[ATTR_PERSONS]:
            published_data[ATTR_ID] = person.get(ATTR_ID)
            published_data[ATTR_NAME] = NETATMO_PERSONS.get(
                published_data[ATTR_ID], DEFAULT_PERSON)
            published_data[ATTR_IS_KNOWN] = person.get(ATTR_IS_KNOWN)
            _LOGGER.debug("webhook data: %s", published_data)
            hass.bus.async_fire(EVENT_RECEIVED, published_data)
    elif data.get(ATTR_EVENT_TYPE) == EVENT_MOVEMENT:
        published_data[ATTR_EVENT_TYPE] = EVENT_MOVEMENT
        published_data[ATTR_HOME_NAME] = data.get(ATTR_HOME_NAME)
        published_data[ATTR_CAMERA_ID] = data.get(ATTR_CAMERA_ID)
        _LOGGER.debug("webhook data: %s", published_data)
        hass.bus.async_fire(EVENT_RECEIVED, published_data)


class CameraData:
    """Get the latest data from Netatmo."""

    def __init__(self, auth, home=None):
        """Initialize the data object."""
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
        global NETATMO_PERSONS
        for person_id, person_data in self.camera_data.persons.items():
            NETATMO_PERSONS[person_id] = person_data.get(ATTR_PSEUDO)

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
