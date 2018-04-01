"""
Support for DoorBird device.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/doorbird/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.components.http import HomeAssistantView
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['DoorBirdPy==0.1.3']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'doorbird'

API_URL = '/api/{}'.format(DOMAIN)

CONF_DOORBELL_EVENTS = 'doorbell_events'
CONF_CUSTOM_URL = 'hass_url_override'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DOORBELL_EVENTS): cv.boolean,
        vol.Optional(CONF_CUSTOM_URL): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

SENSOR_DOORBELL = 'doorbell'


def setup(hass, config):
    """Set up the DoorBird component."""
    from doorbirdpy import DoorBird

    device_ip = config[DOMAIN].get(CONF_HOST)
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)

    device = DoorBird(device_ip, username, password)
    status = device.ready()

    if status[0]:
        _LOGGER.info("Connected to DoorBird at %s as %s", device_ip, username)
        hass.data[DOMAIN] = device
    elif status[1] == 401:
        _LOGGER.error("Authorization rejected by DoorBird at %s", device_ip)
        return False
    else:
        _LOGGER.error("Could not connect to DoorBird at %s: Error %s",
                      device_ip, str(status[1]))
        return False

    if config[DOMAIN].get(CONF_DOORBELL_EVENTS):
        # Provide an endpoint for the device to call to trigger events
        hass.http.register_view(DoorbirdRequestView())

        # Get the URL of this server
        hass_url = hass.config.api.base_url

        # Override it if another is specified in the component configuration
        if config[DOMAIN].get(CONF_CUSTOM_URL):
            hass_url = config[DOMAIN].get(CONF_CUSTOM_URL)
            _LOGGER.info("DoorBird will connect to this instance via %s",
                         hass_url)

        # This will make HA the only service that gets doorbell events
        url = '{}{}/{}'.format(hass_url, API_URL, SENSOR_DOORBELL)
        device.reset_notifications()
        device.subscribe_notification(SENSOR_DOORBELL, url)

    return True


class DoorbirdRequestView(HomeAssistantView):
    """Provide a page for the device to call."""

    requires_auth = False
    url = API_URL
    name = API_URL[1:].replace('/', ':')
    extra_urls = [API_URL + '/{sensor}']

    # pylint: disable=no-self-use
    @asyncio.coroutine
    def get(self, request, sensor):
        """Respond to requests from the device."""
        hass = request.app['hass']
        hass.bus.async_fire('{}_{}'.format(DOMAIN, sensor))
        return 'OK'
