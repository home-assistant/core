"""Component to integrate the Home Assistant cloud."""
import asyncio
import json
import logging
import os

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_START

from . import http_api, iot
from .const import CONFIG_DIR, DOMAIN, SERVERS


REQUIREMENTS = ['warrant==0.5.0']
DEPENDENCIES = ['http']
CONF_MODE = 'mode'
CONF_COGNITO_CLIENT_ID = 'cognito_client_id'
CONF_USER_POOL_ID = 'user_pool_id'
CONF_REGION = 'region'
CONF_RELAYER = 'relayer'
MODE_DEV = 'development'
DEFAULT_MODE = MODE_DEV
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_MODE, default=DEFAULT_MODE):
            vol.In([MODE_DEV] + list(SERVERS)),
        # Change to optional when we include real servers
        vol.Required(CONF_COGNITO_CLIENT_ID): str,
        vol.Required(CONF_USER_POOL_ID): str,
        vol.Required(CONF_REGION): str,
        vol.Required(CONF_RELAYER): str,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the Home Assistant cloud."""
    if DOMAIN in config:
        kwargs = config[DOMAIN]
    else:
        kwargs = {CONF_MODE: DEFAULT_MODE}

    cloud = hass.data[DOMAIN] = Cloud(hass, **kwargs)

    @asyncio.coroutine
    def init_cloud(event):
        """Initialize connection."""
        yield from cloud.initialize()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, init_cloud)

    yield from http_api.async_setup(hass)
    return True


class Cloud:
    """Store the configuration of the cloud connection."""

    def __init__(self, hass, mode, cognito_client_id=None, user_pool_id=None,
                 region=None, relayer=None):
        """Create an instance of Cloud."""
        self.hass = hass
        self.mode = mode
        self.email = None
        self.id_token = None
        self.access_token = None
        self.refresh_token = None
        self.iot = iot.CloudIoT(self)

        if mode == MODE_DEV:
            self.cognito_client_id = cognito_client_id
            self.user_pool_id = user_pool_id
            self.region = region
            self.relayer = relayer

        else:
            info = SERVERS[mode]

            self.cognito_client_id = info['cognito_client_id']
            self.user_pool_id = info['user_pool_id']
            self.region = info['region']
            self.relayer = info['relayer']

    @property
    def is_logged_in(self):
        """Get if cloud is logged in."""
        return self.email is not None

    @property
    def user_info_path(self):
        """Get path to the stored auth."""
        return self.path('{}_auth.json'.format(self.mode))

    @asyncio.coroutine
    def initialize(self):
        """Initialize and load cloud info."""
        def load_config():
            """Load the configuration."""
            # Ensure config dir exists
            path = self.hass.config.path(CONFIG_DIR)
            if not os.path.isdir(path):
                os.mkdir(path)

            user_info = self.user_info_path
            if os.path.isfile(user_info):
                with open(user_info, 'rt') as file:
                    info = json.loads(file.read())
                self.email = info['email']
                self.id_token = info['id_token']
                self.access_token = info['access_token']
                self.refresh_token = info['refresh_token']

        yield from self.hass.async_add_job(load_config)

        if self.email is not None:
            yield from self.iot.connect()

    def path(self, *parts):
        """Get config path inside cloud dir."""
        return self.hass.config.path(CONFIG_DIR, *parts)

    @asyncio.coroutine
    def logout(self):
        """Close connection and remove all credentials."""
        yield from self.iot.disconnect()

        self.email = None
        self.id_token = None
        self.access_token = None
        self.refresh_token = None

        yield from self.hass.async_add_job(
            lambda: os.remove(self.user_info_path))

    def write_user_info(self):
        """Write user info to a file."""
        with open(self.user_info_path, 'wt') as file:
            file.write(json.dumps({
                'email': self.email,
                'id_token': self.id_token,
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
            }, indent=4))
