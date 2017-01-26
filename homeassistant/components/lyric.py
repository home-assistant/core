"""
Support for Honeywell Lyric devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/lyric/
"""
import logging
import socket
import asyncio

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (CONF_FILENAME, HTTP_BAD_REQUEST, HTTP_OK)
from homeassistant.loader import get_component
from homeassistant.components.http import HomeAssistantView

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

REQUIREMENTS = [
    'https://github.com/bramkragten/python-lyric'
    '/archive/v0.0.1-alpha.2.zip'
    '#python-lyric==0.0.1']

DOMAIN = 'lyric'

DATA_LYRIC = 'lyric'

LYRIC_CONFIG_FILE = 'lyric.conf'
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_REDIRECT_URI = 'redirect_uri'
CONF_LOCATIONS = 'locations'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_REDIRECT_URI): cv.string,
        vol.Optional(CONF_LOCATIONS): vol.All(cv.ensure_list, cv.string)
    })
}, extra=vol.ALLOW_EXTRA)

def request_configuration(lyric, hass, config):

    """Request configuration steps from the user."""
    configurator = get_component('configurator')
    if 'lyric' in _CONFIGURING:
        _LOGGER.debug("configurator failed")
        configurator.notify_errors(
            _CONFIGURING['lyric'], "Failed to configure, please try again.")
        return

    def lyric_configuration_callback(data):
        """The actions to do when our configuration callback is called."""
        _LOGGER.debug("configurator callback")
        #url = data.get('url')
        setup_lyric(hass, lyric, config)#url=url

    hass.http.register_view(LyricAuthenticateView(lyric))

    _CONFIGURING['lyric'] = configurator.request_config(
        hass, "Lyric", lyric_configuration_callback,
        description=('To configure Lyric, click Request Authorization below, '
                     'log into your Lyric account, when you get a successfull '
                     'authorize, click continue. '),
                    #'You can also paste the return url under here.'
        link_name='Request Authorization',
        link_url=lyric.getauthorize_url,
        submit_caption="Continue...",
        #fields=[{'id': 'url', 'name': 'Enter the URL', 'type': ''}]
    )


def setup_lyric(hass, lyric, config, url=None):
    """Setup Lyric Devices."""
    if url is not None:
        _LOGGER.debug("url acquired, requesting access token")
        lyric.authorization_response(url)

    if lyric._token is None:
        _LOGGER.debug("no access_token, requesting configuration")
        request_configuration(lyric, hass, config)
        return

    if 'lyric' in _CONFIGURING:
        _LOGGER.debug("configuration done")
        configurator = get_component('configurator')
        configurator.request_done(_CONFIGURING.pop('lyric'))

    _LOGGER.debug("proceeding with setup")
    conf = config[DOMAIN]
    hass.data[DATA_LYRIC] = LyricDevice(hass, conf, lyric)

    _LOGGER.debug("proceeding with discovery")
    discovery.load_platform(hass, 'climate', DOMAIN, {}, config)
#    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
#    discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)
    _LOGGER.debug("setup done")

    return True


def setup(hass, config):
    """Setup the Lyric thermostat component."""
    import lyric

    if 'lyric' in _CONFIGURING:
        return

    conf = config[DOMAIN]
    client_id = conf[CONF_CLIENT_ID]
    client_secret = conf[CONF_CLIENT_SECRET]
    filename = config.get(CONF_FILENAME, LYRIC_CONFIG_FILE)
    token_cache_file = hass.config.path(filename)
    redirect_uri = conf.get(CONF_REDIRECT_URI, hass.config.api.base_url + 
                            '/api/lyric/authenticate')

    lyric = lyric.Lyric(
        token_cache_file=token_cache_file,
        client_id=client_id, client_secret=client_secret, 
        app_name='Home Assistant', redirect_uri=redirect_uri)

    setup_lyric(hass, lyric, config)

    return True


class LyricDevice(object):
    """Structure Lyric functions for hass."""

    def __init__(self, hass, conf, lyric):
        """Init Lyric Devices."""
        self.hass = hass
        self.lyric = lyric

        if CONF_LOCATIONS not in conf:
            self._location = [s.name for s in lyric.locations]
        else:
            self._location = conf[CONF_LOCATIONS]
        _LOGGER.debug("Locations to include: %s", self._location)

    def thermostats(self):
        """Generator returning list of thermostats and their location."""
        try:
            for location in self.lyric.locations:
                if location.name in self._location:
                    for device in location.thermostats:
                        yield (location, device)
                else:
                    _LOGGER.debug("Ignoring location %s, not in %s",
                                  location.name, self._location)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the lyric web service.")

    def waterLeakDetectors(self):
        """Generator returning list of water leak detectors."""
        try:
            for location in self.lyric.locations:
                if location.name in self._location:
                    for device in location.waterLeakDetectors:
                        yield(location, device)
                else:
                    _LOGGER.debug("Ignoring location %s, not in %s",
                                  location.name, self._location)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the lyric web service.")

class LyricAuthenticateView(HomeAssistantView):
    """Handle redirects from lyric oauth2 api, to authenticate."""

    url = '/api/lyric/authenticate'
    name = 'api:lyric:authenticate'
    requires_auth = False

    def __init__(self, lyric):
        """Initialize Lyric Setup url endpoints."""
        self.lyric = lyric

    @asyncio.coroutine
    def get(self, request):
        """Handle a GET request."""

        hass = request.app['hass']
        data = request.GET

        if 'code' not in data or 'state' not in data:
          return self.json_message('Authentication failed, not the right '
                                   'variables, try again.', HTTP_BAD_REQUEST)

        self.lyric.authorization_code(code=data['code'], state=data['state'])

        return self.json_message('Got the respons! You can close this window ' 
                                 'now, and click "Continue" in the configurator.')
