"""Auth providers for Home Assistant."""
import importlib
import logging

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant import requirements
from homeassistant.core import callback
from homeassistant.const import CONF_TYPE, CONF_NAME, CONF_ID
from homeassistant.util.decorator import Registry

from homeassistant.auth.models import Credentials

_LOGGER = logging.getLogger(__name__)
DATA_REQS = 'auth_prov_reqs_processed'

AUTH_PROVIDERS = Registry()

AUTH_PROVIDER_SCHEMA = vol.Schema({
    vol.Required(CONF_TYPE): str,
    vol.Optional(CONF_NAME): str,
    # Specify ID if you have two auth providers for same type.
    vol.Optional(CONF_ID): str,
}, extra=vol.ALLOW_EXTRA)


async def auth_provider_from_config(hass, store, config):
    """Initialize an auth provider from a config."""
    provider_name = config[CONF_TYPE]
    module = await load_auth_provider_module(hass, provider_name)

    if module is None:
        return None

    try:
        config = module.CONFIG_SCHEMA(config)
    except vol.Invalid as err:
        _LOGGER.error('Invalid configuration for auth provider %s: %s',
                      provider_name, humanize_error(config, err))
        return None

    return AUTH_PROVIDERS[provider_name](hass, store, config)


async def load_auth_provider_module(hass, provider):
    """Load an auth provider."""
    try:
        module = importlib.import_module(
            'homeassistant.auth.providers.{}'.format(provider))
    except ImportError:
        _LOGGER.warning('Unable to find auth provider %s', provider)
        return None

    if hass.config.skip_pip or not hasattr(module, 'REQUIREMENTS'):
        return module

    processed = hass.data.get(DATA_REQS)

    if processed is None:
        processed = hass.data[DATA_REQS] = set()
    elif provider in processed:
        return module

    req_success = await requirements.async_process_requirements(
        hass, 'auth provider {}'.format(provider), module.REQUIREMENTS)

    if not req_success:
        return None

    processed.add(provider)
    return module


class AuthProvider:
    """Provider of user authentication."""

    DEFAULT_TITLE = 'Unnamed auth provider'

    def __init__(self, hass, store, config):
        """Initialize an auth provider."""
        self.hass = hass
        self.store = store
        self.config = config

    @property
    def id(self):  # pylint: disable=invalid-name
        """Return id of the auth provider.

        Optional, can be None.
        """
        return self.config.get(CONF_ID)

    @property
    def type(self):
        """Return type of the provider."""
        return self.config[CONF_TYPE]

    @property
    def name(self):
        """Return the name of the auth provider."""
        return self.config.get(CONF_NAME, self.DEFAULT_TITLE)

    async def async_credentials(self):
        """Return all credentials of this provider."""
        users = await self.store.async_get_users()
        return [
            credentials
            for user in users
            for credentials in user.credentials
            if (credentials.auth_provider_type == self.type and
                credentials.auth_provider_id == self.id)
        ]

    @callback
    def async_create_credentials(self, data):
        """Create credentials."""
        return Credentials(
            auth_provider_type=self.type,
            auth_provider_id=self.id,
            data=data,
        )

    # Implement by extending class

    async def async_credential_flow(self, context):
        """Return the data flow for logging in with auth provider."""
        raise NotImplementedError

    async def async_get_or_create_credentials(self, flow_result):
        """Get credentials based on the flow result."""
        raise NotImplementedError

    async def async_user_meta_for_credentials(self, credentials):
        """Return extra user metadata for credentials.

        Will be used to populate info when creating a new user.

        Values to populate:
         - name: string
         - is_active: boolean
        """
        return {}
