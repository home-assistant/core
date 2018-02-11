"""
Component to integrate the Home Assistant cloud.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/cloud/
"""
import asyncio
from datetime import datetime
import json
import logging
import os

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, CONF_REGION, CONF_MODE, CONF_NAME, CONF_TYPE)
from homeassistant.helpers import entityfilter, config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util
from homeassistant.components.alexa import smart_home as alexa_sh
from homeassistant.components.google_assistant import smart_home as ga_sh

from . import http_api, iot
from .const import CONFIG_DIR, DOMAIN, SERVERS

REQUIREMENTS = ['warrant==0.6.1']

_LOGGER = logging.getLogger(__name__)

CONF_ALEXA = 'alexa'
CONF_ALIASES = 'aliases'
CONF_COGNITO_CLIENT_ID = 'cognito_client_id'
CONF_ENTITY_CONFIG = 'entity_config'
CONF_FILTER = 'filter'
CONF_GOOGLE_ACTIONS = 'google_actions'
CONF_RELAYER = 'relayer'
CONF_USER_POOL_ID = 'user_pool_id'

DEFAULT_MODE = 'production'
DEPENDENCIES = ['http']

MODE_DEV = 'development'

ALEXA_ENTITY_SCHEMA = vol.Schema({
    vol.Optional(alexa_sh.CONF_DESCRIPTION): cv.string,
    vol.Optional(alexa_sh.CONF_DISPLAY_CATEGORIES): cv.string,
    vol.Optional(alexa_sh.CONF_NAME): cv.string,
})

GOOGLE_ENTITY_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_TYPE): vol.In(ga_sh.MAPPING_COMPONENT),
    vol.Optional(CONF_ALIASES): vol.All(cv.ensure_list, [cv.string])
})

ASSISTANT_SCHEMA = vol.Schema({
    vol.Optional(
        CONF_FILTER,
        default=lambda: entityfilter.generate_filter([], [], [], [])
    ): entityfilter.FILTER_SCHEMA,
})

ALEXA_SCHEMA = ASSISTANT_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: ALEXA_ENTITY_SCHEMA}
})

GACTIONS_SCHEMA = ASSISTANT_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: GOOGLE_ENTITY_SCHEMA}
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_MODE, default=DEFAULT_MODE):
            vol.In([MODE_DEV] + list(SERVERS)),
        # Change to optional when we include real servers
        vol.Optional(CONF_COGNITO_CLIENT_ID): str,
        vol.Optional(CONF_USER_POOL_ID): str,
        vol.Optional(CONF_REGION): str,
        vol.Optional(CONF_RELAYER): str,
        vol.Optional(CONF_ALEXA): ALEXA_SCHEMA,
        vol.Optional(CONF_GOOGLE_ACTIONS): GACTIONS_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the Home Assistant cloud."""
    if DOMAIN in config:
        kwargs = dict(config[DOMAIN])
    else:
        kwargs = {CONF_MODE: DEFAULT_MODE}

    alexa_conf = kwargs.pop(CONF_ALEXA, None) or ALEXA_SCHEMA({})

    if CONF_GOOGLE_ACTIONS not in kwargs:
        kwargs[CONF_GOOGLE_ACTIONS] = GACTIONS_SCHEMA({})

    kwargs[CONF_ALEXA] = alexa_sh.Config(
        should_expose=alexa_conf[CONF_FILTER],
        entity_config=alexa_conf.get(CONF_ENTITY_CONFIG),
    )

    cloud = hass.data[DOMAIN] = Cloud(hass, **kwargs)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, cloud.async_start)
    yield from http_api.async_setup(hass)
    return True


class Cloud:
    """Store the configuration of the cloud connection."""

    def __init__(self, hass, mode, alexa, google_actions,
                 cognito_client_id=None, user_pool_id=None, region=None,
                 relayer=None):
        """Create an instance of Cloud."""
        self.hass = hass
        self.mode = mode
        self.alexa_config = alexa
        self._google_actions = google_actions
        self._gactions_config = None
        self.jwt_keyset = None
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
        return self.id_token is not None

    @property
    def subscription_expired(self):
        """Return a boolean if the subscription has expired."""
        return dt_util.utcnow() > self.expiration_date

    @property
    def expiration_date(self):
        """Return the subscription expiration as a UTC datetime object."""
        return datetime.combine(
            dt_util.parse_date(self.claims['custom:sub-exp']),
            datetime.min.time()).replace(tzinfo=dt_util.UTC)

    @property
    def claims(self):
        """Return the claims from the id token."""
        return self._decode_claims(self.id_token)

    @property
    def user_info_path(self):
        """Get path to the stored auth."""
        return self.path('{}_auth.json'.format(self.mode))

    @property
    def gactions_config(self):
        """Return the Google Assistant config."""
        if self._gactions_config is None:
            conf = self._google_actions

            def should_expose(entity):
                """If an entity should be exposed."""
                return conf['filter'](entity.entity_id)

            self._gactions_config = ga_sh.Config(
                should_expose=should_expose,
                agent_user_id=self.claims['cognito:username'],
                entity_config=conf.get(CONF_ENTITY_CONFIG),
            )

        return self._gactions_config

    def path(self, *parts):
        """Get config path inside cloud dir.

        Async friendly.
        """
        return self.hass.config.path(CONFIG_DIR, *parts)

    @asyncio.coroutine
    def logout(self):
        """Close connection and remove all credentials."""
        yield from self.iot.disconnect()

        self.id_token = None
        self.access_token = None
        self.refresh_token = None
        self._gactions_config = None

        yield from self.hass.async_add_job(
            lambda: os.remove(self.user_info_path))

    def write_user_info(self):
        """Write user info to a file."""
        with open(self.user_info_path, 'wt') as file:
            file.write(json.dumps({
                'id_token': self.id_token,
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
            }, indent=4))

    @asyncio.coroutine
    def async_start(self, _):
        """Start the cloud component."""
        success = yield from self._fetch_jwt_keyset()

        # Fetching keyset can fail if internet is not up yet.
        if not success:
            self.hass.helpers.async_call_later(5, self.async_start)
            return

        def load_config():
            """Load config."""
            # Ensure config dir exists
            path = self.hass.config.path(CONFIG_DIR)
            if not os.path.isdir(path):
                os.mkdir(path)

            user_info = self.user_info_path
            if not os.path.isfile(user_info):
                return None

            with open(user_info, 'rt') as file:
                return json.loads(file.read())

        info = yield from self.hass.async_add_job(load_config)

        if info is None:
            return

        # Validate tokens
        try:
            for token in 'id_token', 'access_token':
                self._decode_claims(info[token])
        except ValueError as err:  # Raised when token is invalid
            _LOGGER.warning("Found invalid token %s: %s", token, err)
            return

        self.id_token = info['id_token']
        self.access_token = info['access_token']
        self.refresh_token = info['refresh_token']

        self.hass.add_job(self.iot.connect())

    @asyncio.coroutine
    def _fetch_jwt_keyset(self):
        """Fetch the JWT keyset for the Cognito instance."""
        session = async_get_clientsession(self.hass)
        url = ("https://cognito-idp.us-east-1.amazonaws.com/"
               "{}/.well-known/jwks.json".format(self.user_pool_id))

        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                req = yield from session.get(url)
                self.jwt_keyset = yield from req.json()

            return True

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error fetching Cognito keyset: %s", err)
            return False

    def _decode_claims(self, token):
        """Decode the claims in a token."""
        from jose import jwt, exceptions as jose_exceptions
        try:
            header = jwt.get_unverified_header(token)
        except jose_exceptions.JWTError as err:
            raise ValueError(str(err)) from None
        kid = header.get('kid')

        if kid is None:
            raise ValueError("No kid in header")

        # Locate the key for this kid
        key = None
        for key_dict in self.jwt_keyset['keys']:
            if key_dict['kid'] == kid:
                key = key_dict
                break
        if not key:
            raise ValueError(
                "Unable to locate kid ({}) in keyset".format(kid))

        try:
            return jwt.decode(
                token, key, audience=self.cognito_client_id, options={
                    'verify_exp': False,
                })
        except jose_exceptions.JWTError as err:
            raise ValueError(str(err)) from None
