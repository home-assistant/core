"""
Support for Honeywell Lyric devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/lyric
"""
import asyncio
import logging
import socket

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_SCAN_INTERVAL, HTTP_BAD_REQUEST, HTTP_OK
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

REQUIREMENTS = ['python-lyric==1.1.4']

DOMAIN = 'lyric'

DATA_LYRIC = 'lyric'

LYRIC_CONFIG_FILE = 'lyric.conf'
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_REDIRECT_URI = 'redirect_uri'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_REDIRECT_URI): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=270): cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)


def request_configuration(lyric, hass, config):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    if 'lyric' in _CONFIGURING:
        _LOGGER.warning("Honeywell Lyric configuration failed.")
        configurator.notify_errors(
            _CONFIGURING['lyric'], "Failed to configure, please try again.")
        return

    def lyric_configuration_callback(data):
        """Run when the configuration callback is called."""
        _LOGGER.debug("Configurator callback")
        setup_lyric(hass, lyric, config)

    hass.http.register_view(LyricAuthenticateView(lyric))

    _CONFIGURING['lyric'] = configurator.request_config(
        "Honeywell Lyric", lyric_configuration_callback,
        description=('To configure Lyric, click Request Authorization below, '
                     'then log into your Lyric account and authorize your'
                     ' devices. Once you get a success message you can '
                     ' click `Continue`.'),
        link_name='Request Authorization',
        link_url=lyric.getauthorize_url,
        submit_caption="Continue",
    )


def setup_lyric(hass, lyric, config, url=None):
    """Set up the Lyric devices."""
    if url is not None:
        _LOGGER.debug("url acquired, requesting access token")
        lyric.authorization_response(url)

    # pylint: disable=protected-access
    if lyric._token is None:
        _LOGGER.debug("No access_token, requesting configuration")
        request_configuration(lyric, hass, config)
        return

    if 'lyric' in _CONFIGURING:
        _LOGGER.debug("Configuration done")
        configurator = hass.components.configurator
        configurator.request_done(_CONFIGURING.pop('lyric'))

    _LOGGER.debug("Proceeding with setup")
    conf = config[DOMAIN]
    hass.data[DATA_LYRIC] = LyricDevice(hass, conf, lyric)

    _LOGGER.debug(hass.data[DATA_LYRIC].lyric.locations)
    _LOGGER.debug("Proceeding with discovery of platforms")
    conf.pop(CONF_CLIENT_ID)
    conf.pop(CONF_CLIENT_SECRET)
    discovery.load_platform(hass, 'climate', DOMAIN, conf, config)
    discovery.load_platform(hass, 'sensor', DOMAIN, conf, config)
    _LOGGER.debug("Setup done of component")

    return True


def setup(hass, config):
    """Set up the Lyric component."""
    import lyric

    if 'lyric' in _CONFIGURING:
        return

    conf = config[DOMAIN]
    client_id = conf[CONF_CLIENT_ID]
    client_secret = conf[CONF_CLIENT_SECRET]
    cache_ttl = conf[CONF_SCAN_INTERVAL]
    filename = LYRIC_CONFIG_FILE
    token_cache_file = hass.config.path(filename)
    redirect_uri = conf.get(
        CONF_REDIRECT_URI,
        '{}/api/lyric/authenticate'.format(hass.config.api.base_url)
    )

    lyric = lyric.Lyric(
        token_cache_file=token_cache_file,
        client_id=client_id, client_secret=client_secret,
        app_name='Home Assistant', redirect_uri=redirect_uri,
        cache_ttl=cache_ttl)

    setup_lyric(hass, lyric, config)

    return True


class LyricDevice(object):
    """Structure Lyric functions for hass."""

    def __init__(self, hass, conf, lyric):
        """Init Lyric devices."""
        self.hass = hass
        self.lyric = lyric

        if not lyric.locations:
            _LOGGER.warning("No locations found.")
            return

        self._location = [location.name for location in lyric.locations]

    def thermostats(self):
        """Generate a list of thermostats and their location."""
        try:
            for location in self.lyric.locations:
                if location.name in self._location:
                    for device in location.thermostats:
                        yield (location, device)
                else:
                    _LOGGER.debug("Ignoring location %s, not in %s",
                                  location.name, self._location)
        except TypeError:
            _LOGGER.error(
                "Connection error logging into the Lyric web service.")


class LyricAuthenticateView(HomeAssistantView):
    """Handle redirects from lyric oauth2 api, to authenticate."""
    url = '/api/lyric/authenticate'
    name = 'api:lyric:authenticate'
    requires_auth = False

    def __init__(self, lyric):
        """Initialize Lyric Setup url endpoints."""
        self.lyric = lyric

    @asyncio.coroutine
    async def get(self, request):
        """Handle a GET request."""
        # hass = request.app['hass']
        data = request.query

        if 'code' not in data or 'state' not in data:
            return self.json_message('Authentication failed, not the right '
                                     'variables, try again.', HTTP_BAD_REQUEST)

        self.lyric.authorization_code(code=data['code'], state=data['state'])

        return self.json_message('Honeywell Lyric now authenticated. You can'
                                 'now close this window/tab and click '
                                 '`Continue` in the dialog.')
