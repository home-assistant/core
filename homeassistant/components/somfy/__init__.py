"""
Support for Somfy hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/somfy/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pymfy==0.4.2']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

DOMAIN = 'somfy'

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

ATTR_ACCESS_TOKEN = 'access_token'
ATTR_REFRESH_TOKEN = 'refresh_token'
ATTR_CLIENT_ID = 'client_id'
ATTR_CLIENT_SECRET = 'client_secret'

SOMFY_AUTH_CALLBACK_PATH = '/auth/somfy/callback'
SOMFY_AUTH_START = '/auth/somfy'

DEFAULT_CACHE_PATH = '.somfy'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

SOMFY_COMPONENTS = ['cover']


def setup(hass, config):
    """Set up the Somfy component."""
    from pymfy.api.somfy_api import SomfyApi

    hass.data[DOMAIN] = {}

    # This is called to create the redirect so the user can Authorize Home .
    redirect_uri = '{}{}'.format(
        hass.config.api.base_url, SOMFY_AUTH_CALLBACK_PATH)
    conf = config[DOMAIN]
    api = SomfyApi(conf.get(CONF_CLIENT_ID),
                   conf.get(CONF_CLIENT_SECRET),
                   redirect_uri, hass.config.path(DEFAULT_CACHE_PATH))

    if not api.token:
        hass.http.register_view(SomfyAuthCallbackView(
            config, api.request_token))
        request_configuration(hass, api)
    else:
        hass.data[DOMAIN]['api'] = api
        update_all_devices(hass)
        for component in SOMFY_COMPONENTS:
            discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


def request_configuration(hass, api):
    """Request Spotify authorization."""
    configurator = hass.components.configurator
    url, _ = api.get_authorization_url()
    hass.data[DOMAIN]['configurator'] = configurator.request_config(
        'Somfy', lambda _: None,
        link_name='Link Somfy account',
        link_url=url,
        description='To link your Somfy account, '
                    'click the link, login, and authorize:',
        submit_caption='I authorized successfully')


class SomfyAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    url = SOMFY_AUTH_CALLBACK_PATH
    name = 'auth:somfy:callback'
    requires_auth = False

    def __init__(self, config, request_token):
        """Initialize the OAuth callback view."""
        self.config = config
        self.request_token = request_token

    @callback
    def get(self, request):
        """Finish OAuth callback request."""
        from aiohttp import web

        hass = request.app['hass']

        response_message = """Somfy has been successfully authorized!
         You can close this window now! For the best results you should reboot
         HomeAssistant"""
        html_response = """<html><head><title>Somfy Auth</title></head>
                <body><h1>{}</h1></body></html>"""

        self.request_token(str(request.url))
        hass.async_add_job(setup, hass, self.config)
        return web.Response(text=html_response.format(response_message),
                            content_type='text/html')


class SomfyEntity(Entity):
    """Representation a base Somfy device."""

    def __init__(self, device, hass):
        """Initialize the Somfy device."""
        self.hass = hass
        self.device = device
        self.api = hass.data[DOMAIN]['api']

    @property
    def unique_id(self):
        """Return the unique id for the camera sensor."""
        return self.device.id

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.name

    def update(self):
        update_all_devices(self.hass)
        devices = self.hass.data[DOMAIN]['devices']
        self.device = next((d for d in devices if d.id == self.device.id),
                           self.device)


@Throttle(MIN_TIME_BETWEEN_UPDATES)
def update_all_devices(hass):
    """Update state of the device."""
    from requests import HTTPError
    try:
        data = hass.data[DOMAIN]
        data['devices'] = data['api'].get_devices()
    except HTTPError as error:
        _LOGGER.error("Cannot update devices %s.", error)
