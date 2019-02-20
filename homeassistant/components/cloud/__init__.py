"""
Component to integrate the Home Assistant cloud.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/cloud/
"""
from datetime import datetime, timedelta
import json
import logging
import os

import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, CLOUD_NEVER_EXPOSED_ENTITIES, CONF_REGION,
    CONF_MODE, CONF_NAME)
from homeassistant.helpers import entityfilter, config_validation as cv
from homeassistant.util import dt as dt_util
from homeassistant.components.alexa import smart_home as alexa_sh
from homeassistant.components.google_assistant import helpers as ga_h
from homeassistant.components.google_assistant import const as ga_c

from . import http_api, iot, auth_api, prefs, cloudhooks
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
CONF_GOOGLE_ACTIONS_SYNC_URL = 'google_actions_sync_url'
CONF_SUBSCRIPTION_INFO_URL = 'subscription_info_url'
CONF_CLOUDHOOK_CREATE_URL = 'cloudhook_create_url'

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
    vol.Optional(CONF_ALIASES): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ga_c.CONF_ROOM_HINT): cv.string,
})

ASSISTANT_SCHEMA = vol.Schema({
    vol.Optional(CONF_FILTER, default={}): entityfilter.FILTER_SCHEMA,
})

ALEXA_SCHEMA = ASSISTANT_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: ALEXA_ENTITY_SCHEMA}
})

GACTIONS_SCHEMA = ASSISTANT_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: GOOGLE_ENTITY_SCHEMA},
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
        vol.Optional(CONF_GOOGLE_ACTIONS_SYNC_URL): str,
        vol.Optional(CONF_SUBSCRIPTION_INFO_URL): str,
        vol.Optional(CONF_CLOUDHOOK_CREATE_URL): str,
        vol.Optional(CONF_ALEXA): ALEXA_SCHEMA,
        vol.Optional(CONF_GOOGLE_ACTIONS): GACTIONS_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Initialize the Home Assistant cloud."""
    if DOMAIN in config:
        kwargs = dict(config[DOMAIN])
    else:
        kwargs = {CONF_MODE: DEFAULT_MODE}

    alexa_conf = kwargs.pop(CONF_ALEXA, None) or ALEXA_SCHEMA({})

    if CONF_GOOGLE_ACTIONS not in kwargs:
        kwargs[CONF_GOOGLE_ACTIONS] = GACTIONS_SCHEMA({})

    kwargs[CONF_ALEXA] = alexa_sh.Config(
        endpoint=None,
        async_get_access_token=None,
        should_expose=alexa_conf[CONF_FILTER],
        entity_config=alexa_conf.get(CONF_ENTITY_CONFIG),
    )

    cloud = hass.data[DOMAIN] = Cloud(hass, **kwargs)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, cloud.async_start)
    await http_api.async_setup(hass)
    return True


class Cloud:
    """Store the configuration of the cloud connection."""

    def __init__(self, hass, mode, alexa, google_actions,
                 cognito_client_id=None, user_pool_id=None, region=None,
                 relayer=None, google_actions_sync_url=None,
                 subscription_info_url=None, cloudhook_create_url=None):
        """Create an instance of Cloud."""
        self.hass = hass
        self.mode = mode
        self.alexa_config = alexa
        self.google_actions_user_conf = google_actions
        self._gactions_config = None
        self.prefs = prefs.CloudPreferences(hass)
        self.id_token = None
        self.access_token = None
        self.refresh_token = None
        self.iot = iot.CloudIoT(self)
        self.cloudhooks = cloudhooks.Cloudhooks(self)

        if mode == MODE_DEV:
            self.cognito_client_id = cognito_client_id
            self.user_pool_id = user_pool_id
            self.region = region
            self.relayer = relayer
            self.google_actions_sync_url = google_actions_sync_url
            self.subscription_info_url = subscription_info_url
            self.cloudhook_create_url = cloudhook_create_url

        else:
            info = SERVERS[mode]

            self.cognito_client_id = info['cognito_client_id']
            self.user_pool_id = info['user_pool_id']
            self.region = info['region']
            self.relayer = info['relayer']
            self.google_actions_sync_url = info['google_actions_sync_url']
            self.subscription_info_url = info['subscription_info_url']
            self.cloudhook_create_url = info['cloudhook_create_url']

    @property
    def is_logged_in(self):
        """Get if cloud is logged in."""
        return self.id_token is not None

    @property
    def subscription_expired(self):
        """Return a boolean if the subscription has expired."""
        return dt_util.utcnow() > self.expiration_date + timedelta(days=7)

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
            conf = self.google_actions_user_conf

            def should_expose(entity):
                """If an entity should be exposed."""
                if entity.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
                    return False

                return conf['filter'](entity.entity_id)

            self._gactions_config = ga_h.Config(
                should_expose=should_expose,
                allow_unlock=self.prefs.google_allow_unlock,
                agent_user_id=self.claims['cognito:username'],
                entity_config=conf.get(CONF_ENTITY_CONFIG),
            )

        return self._gactions_config

    def path(self, *parts):
        """Get config path inside cloud dir.

        Async friendly.
        """
        return self.hass.config.path(CONFIG_DIR, *parts)

    async def fetch_subscription_info(self):
        """Fetch subscription info."""
        await self.hass.async_add_executor_job(auth_api.check_token, self)
        websession = self.hass.helpers.aiohttp_client.async_get_clientsession()
        return await websession.get(
            self.subscription_info_url, headers={
                'authorization': self.id_token
            })

    async def logout(self):
        """Close connection and remove all credentials."""
        await self.iot.disconnect()

        self.id_token = None
        self.access_token = None
        self.refresh_token = None
        self._gactions_config = None

        await self.hass.async_add_job(
            lambda: os.remove(self.user_info_path))

    def write_user_info(self):
        """Write user info to a file."""
        with open(self.user_info_path, 'wt') as file:
            file.write(json.dumps({
                'id_token': self.id_token,
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
            }, indent=4))

    async def async_start(self, _):
        """Start the cloud component."""
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

        info = await self.hass.async_add_job(load_config)
        await self.prefs.async_initialize()

        if info is None:
            return

        self.id_token = info['id_token']
        self.access_token = info['access_token']
        self.refresh_token = info['refresh_token']

        self.hass.add_job(self.iot.connect())

    def _decode_claims(self, token):  # pylint: disable=no-self-use
        """Decode the claims in a token."""
        from jose import jwt
        return jwt.get_unverified_claims(token)
