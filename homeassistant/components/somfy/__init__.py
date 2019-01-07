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

API = 'api'

DEVICES = 'devices'

REQUIREMENTS = ['pymfy==0.4.4']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

DOMAIN = 'somfy'

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

NOTIFICATION_CB_ID = 'somfy_cb_notification'
NOTIFICATION_OK_ID = 'somfy_ok_notification'
NOTIFICATION_TITLE = 'Somfy Setup'

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
    is_ready = False

    # This is called to create the redirect so the user can Authorize Home .
    redirect_uri = '{}{}'.format(
        hass.config.api.base_url, SOMFY_AUTH_CALLBACK_PATH)
    conf = config[DOMAIN]
    api = SomfyApi(conf.get(CONF_CLIENT_ID),
                   conf.get(CONF_CLIENT_SECRET),
                   redirect_uri, hass.config.path(DEFAULT_CACHE_PATH))
    hass.data[DOMAIN][API] = api

    if not api.token:
        authorization_url, _ = api.get_authorization_url()
        hass.components.persistent_notification.create(
            'In order to authorize Home Assistant to view your Somfy devices'
            ' you must visit this <a href="{}" target="_blank">link</a>.'
            .format(authorization_url),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_CB_ID
        )
        hass.http.register_view(SomfyAuthCallbackView(config))
        is_ready = True
    else:
        if update_all_devices(hass):
            is_ready = True
            for component in SOMFY_COMPONENTS:
                discovery.load_platform(hass, component, DOMAIN, {}, config)

    return is_ready


class SomfyAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    url = SOMFY_AUTH_CALLBACK_PATH
    name = 'auth:somfy:callback'
    requires_auth = False

    def __init__(self, config):
        """Initialize the OAuth callback view."""
        self.config = config

    @callback
    def get(self, request):
        """Finish OAuth callback request."""
        from aiohttp import web
        from oauthlib.oauth2 import MismatchingStateError
        from oauthlib.oauth2 import InsecureTransportError

        hass = request.app['hass']
        response = web.HTTPFound('/')

        try:
            code = request.query.get('code')
            hass.data[DOMAIN][API].request_token(code=code)
            hass.async_add_job(setup, hass, self.config)
            hass.components.persistent_notification.dismiss(NOTIFICATION_CB_ID)
            hass.components.persistent_notification.create(
                "Somfy has been successfully authorized!",
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_CB_ID
            )
        except MismatchingStateError:
            _LOGGER.error("OAuth state not equal in request and response.",
                          exc_info=True)
        except InsecureTransportError:
            _LOGGER.error("Somfy redirect URI %s is insecure.", request.url,
                          exc_info=True)

        return response


class SomfyEntity(Entity):
    """Representation of a generic Somfy device."""

    def __init__(self, device, hass):
        """Initialize the Somfy device."""
        self.hass = hass
        self.device = device
        self.api = hass.data[DOMAIN][API]

    @property
    def unique_id(self):
        """Return the unique id base on the id returned by Somfy."""
        return self.device.id

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.name

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self.unique_id)},
            'name': self.name,
            'model': self.device.type,
            'via_hub': (DOMAIN, self.device.site_id),
        }

    def update(self):
        """Update the device with the latest data."""
        update_all_devices(self.hass)
        devices = self.hass.data[DOMAIN][DEVICES]
        self.device = next((d for d in devices if d.id == self.device.id),
                           self.device)

    def has_capability(self, capability):
        """Test if device has a capability."""
        capabilities = self.device.capabilities
        return bool([c for c in capabilities if c.name == capability])


@Throttle(MIN_TIME_BETWEEN_UPDATES)
def update_all_devices(hass):
    """Update all the devices."""
    from requests import HTTPError
    try:
        data = hass.data[DOMAIN]
        data[DEVICES] = data[API].get_devices()
    except HTTPError:
        _LOGGER.warning("Cannot update devices.", exc_info=True)
        return False
    return True
