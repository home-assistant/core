"""Auth providers for Home Assistant."""
import importlib
import logging
from collections import OrderedDict

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant import data_entry_flow, requirements
from homeassistant.core import callback
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.util import dt as dt_util
from homeassistant.util.decorator import Registry

from homeassistant.auth.models import Credentials
from homeassistant.auth.mfa_modules import SESSION_EXPIRATION

_LOGGER = logging.getLogger(__name__)
DATA_REQS = 'auth_prov_reqs_processed'

AUTH_PROVIDERS = Registry()

AUTH_PROVIDER_SCHEMA = vol.Schema({
    vol.Required(CONF_TYPE): str,
    vol.Optional(CONF_NAME): str,
    # Specify ID if you have two auth providers for same type.
    vol.Optional(CONF_ID): str,
})


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

    async def async_login_flow(self):
        """Return the data flow for logging in with auth provider.

        Auth provider should extend LoginFlow
        """
        return LoginFlow(self)

    async def async_get_or_create_credentials(self, flow_result):
        """Get credentials based on the flow result."""
        raise NotImplementedError

    async def async_user_meta_for_credentials(self, credentials):
        """Return extra user metadata for credentials.

        Will be used to populate info when creating a new user.
        """
        return {}


class LoginFlow(data_entry_flow.FlowHandler):
    """Handler for the login flow."""

    def __init__(self, auth_provider: AuthProvider):
        """Initialize the login flow."""
        self._auth_provider = auth_provider
        self._auth_module_id = None
        self._auth_modules = []
        self._auth_manager = auth_provider.hass.auth
        self._user = None
        self._username = None
        self.created_at = dt_util.utcnow()

    async def async_step_init(self, user_input=None):
        """Handle the first step of login flow.

        Return self.async_show_form(step_id='init') if user_input == None.
        Return await self.async_finish(username) if login init step pass.
        """
        raise NotImplementedError

    async def async_step_select_mfa_module(self, user_input=None):
        """Handle the step of select mfa module."""
        errors = {}

        if user_input is not None:
            auth_module = user_input.get('multi_factor_auth_module')
            if auth_module in self._auth_modules:
                self._auth_module_id = auth_module
                return await self.async_step_mfa()
            else:
                errors['base'] = 'invalid_auth_module'

        schema = OrderedDict()
        schema['multi_factor_auth_module'] = vol.In(self._auth_modules)

        return self.async_show_form(
            step_id='select_mfa_module',
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_mfa(self, user_input=None):
        """Handle the step of mfa validation."""
        errors = {}

        auth_module = self._auth_manager.get_auth_mfa_module(
            self._auth_module_id)
        if auth_module is None:
            # Given an invalid input to async_ste[_select_mfa_module
            # will show invalid_auth_module error
            return await self.async_step_select_mfa_module(
                user_input={'multi_factor_auth_module': None})

        if user_input is not None:
            expires = self.created_at + SESSION_EXPIRATION
            if dt_util.utcnow() > expires:
                errors['base'] = 'login_expired'
            else:
                result = await auth_module.async_validation(
                    self._user.id, user_input)
                if not result:
                    errors['base'] = 'invalid_auth'

            if not errors:
                return await self.async_finish(self._username, mfa_valid=True)

        return self.async_show_form(
            step_id='mfa',
            data_schema=auth_module.input_schema,
            errors=errors,
        )

    async def async_finish(self, username, mfa_valid=False):
        """Handle the pass of login flow."""
        if not mfa_valid:
            self._username = username

            # We need get user from username, so we need get credential first
            # async_get_or_create_credentials would not save data, it is safe
            # to be called here. It will be called later in end of workflow.
            credentials = await self._auth_provider.\
                async_get_or_create_credentials({'username': username})

            # multi-factor module cannot enabled for new credential
            # which has not linked to a user yet
            if not credentials.is_new:
                self._user = await self._auth_manager.\
                    async_get_user_by_credentials(credentials)

                # module in user.mfa_modules may not loaded
                # the config may have changed after the user enabled module
                # we need double check available mfa_modules for this user
                if self._user and self._user.mfa_modules:
                    modules = [m_id for m_id in self._user.mfa_modules
                               if self._auth_manager.
                               get_auth_mfa_module(m_id)]

                    if modules:
                        self._auth_modules = modules
                        if len(self._auth_modules) == 1:
                            self._auth_module_id = self._auth_modules[0]
                            return await self.async_step_mfa()
                        # need select mfa module first
                        return await self.async_step_select_mfa_module()

        # new credential or no mfa_module enabled or passed mfa validate
        return self.async_create_entry(
            title=self._auth_provider.name,
            data={'username': username}
        )
