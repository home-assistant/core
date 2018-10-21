"""
Support for DoorBird device.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/doorbird/
"""

import asyncio
import datetime
import logging
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_HOST, CONF_USERNAME, \
    CONF_PASSWORD, CONF_NAME, CONF_DEVICES, CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify

REQUIREMENTS = ['DoorBirdPy==0.1.3']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'doorbird'

API_URL = '/api/{}'.format(DOMAIN)

CONF_DOORBELL_EVENTS = 'doorbell_events'
CONF_CUSTOM_URL = 'hass_url_override'
CONF_TOKEN = 'token'

DOORBELL_EVENT = 'doorbell'
MOTION_EVENT = 'motionsensor'

# Sensor types: Name, device_class, event
SENSOR_TYPES = {
    'doorbell': ['Button', 'occupancy', DOORBELL_EVENT],
    'motion': ['Motion', 'motion', MOTION_EVENT],
}

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_CUSTOM_URL): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA])
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the DoorBird component."""
    from doorbirdpy import DoorBird

    token = config[DOMAIN].get(CONF_TOKEN)

    # Provide an endpoint for the doorstations to call to trigger events
    hass.http.register_view(DoorbirdRequestView(token))

    doorstations = []

    for index, doorstation_config in enumerate(config[DOMAIN][CONF_DEVICES]):
        device_ip = doorstation_config.get(CONF_HOST)
        username = doorstation_config.get(CONF_USERNAME)
        password = doorstation_config.get(CONF_PASSWORD)
        custom_url = doorstation_config.get(CONF_CUSTOM_URL)
        events = doorstation_config.get(CONF_MONITORED_CONDITIONS)
        name = (doorstation_config.get(CONF_NAME)
                or 'DoorBird {}'.format(index + 1))

        device = DoorBird(device_ip, username, password)
        status = device.ready()

        if status[0]:
            _LOGGER.info("Connected to DoorBird at %s as %s", device_ip,
                         username)
            doorstation = ConfiguredDoorbird(device, name, events, custom_url,
                                             token)
            doorstations.append(doorstation)
        elif status[1] == 401:
            _LOGGER.error("Authorization rejected by DoorBird at %s",
                          device_ip)
            return False
        else:
            _LOGGER.error("Could not connect to DoorBird at %s: Error %s",
                          device_ip, str(status[1]))
            return False

        # SETUP EVENT SUBSCRIBERS
        if events is not None:
            # This will make HA the only service that receives events.
            doorstation.device.reset_notifications()

            # Subscribe to doorbell or motion events
            subscribe_events(hass, doorstation)

    hass.data[DOMAIN] = doorstations

    return True


def get_doorstation_by_slug(hass, slug):
    """Get doorstation by slug"""
    for doorstation in hass.data[DOMAIN]:
        if slugify(doorstation.name) in slug:
            return doorstation


def handle_event(event):
    """Dummy handler used to register events in GUI"""
    return None


def subscribe_events(hass, doorstation):
    """Initialize the subscriber."""
    for sensor_type in doorstation.monitored_events:
        name = '{} {}'.format(doorstation.name,
                              SENSOR_TYPES[sensor_type][0])
        event_type = SENSOR_TYPES[sensor_type][2]

        # Get the URL of this server
        hass_url = hass.config.api.base_url

        # Override url if another is specified onth configuration
        if doorstation.custom_url is not None:
            hass_url = doorstation.custom_url

        slug = slugify(name)

        url = '{}{}/{}?token={}'.format(hass_url, API_URL, slug,
                                        doorstation.token)

        _LOGGER.info("DoorBird will connect to this instance via %s",
                     url)

        _LOGGER.info("You may use the following event name for automations"
                     ": %s_%s", DOMAIN, slug)

        doorstation.device.subscribe_notification(event_type, url)

        # Register a dummy listener so event is listed in GUI
        hass.bus.listen('{}_{}'.format(DOMAIN, slug), handle_event)


class ConfiguredDoorbird():
    """Attach additional information to pass along with configured device."""

    def __init__(self, device, name, events=None, custom_url=None, token=None):
        """Initialize configured device."""
        self._name = name
        self._device = device
        self._custom_url = custom_url
        self._monitored_events = events
        self._token = token

    @property
    def name(self):
        """Get custom device name."""
        return self._name

    @property
    def device(self):
        """Get the configured device."""
        return self._device

    @property
    def custom_url(self):
        """Get custom url for device."""
        return self._custom_url

    @property
    def monitored_events(self):
        """Get monitored events."""
        if self._monitored_events is None:
            return []

        return self._monitored_events

    @property
    def token(self):
        """Get token used to authenticate event endpoint"""
        return self._token

    def get_event_data(self):
        """Get data to pass along with HA event."""
        return {
            'timestamp': datetime.datetime.now(),
            'live_video_url': self._device.live_video_url,
            'live_image_url': self._device.live_image_url,
            'rtsp_live_video_url': self._device.rtsp_live_video_url,
            'html5_viewer_url': self._device.html5_viewer_url
        }


class DoorbirdRequestView(HomeAssistantView):
    """Provide a page for the device to call."""

    requires_auth = False
    url = API_URL
    name = API_URL[1:].replace('/', ':')
    extra_urls = [API_URL + '/{sensor}']

    def __init__(self, token):
        HomeAssistantView.__init__(self)
        self._token = token

    # pylint: disable=no-self-use
    async def get(self, request, sensor):
        """Respond to requests from the device."""

        request_token = request.query.get('token')

        authenticated = request_token == self._token

        if request_token == '' or not authenticated:
            return self.json_message('Unauthorized.')

        hass = request.app['hass']

        doorstation = get_doorstation_by_slug(hass, sensor)

        if doorstation is not None:
            event_data = doorstation.get_event_data()
        else:
            event_data = {}

        hass.bus.async_fire('{}_{}'.format(DOMAIN, sensor), event_data)

        return 'OK'
