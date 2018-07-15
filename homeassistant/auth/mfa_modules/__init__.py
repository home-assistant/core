"""Plugable auth modules for Home Assistant."""
import importlib
import logging
from datetime import timedelta

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant import requirements
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.util.decorator import Registry

MULTI_FACTOR_AUTH_MODULES = Registry()

MULTI_FACTOR_AUTH_MODULE_SCHEMA = vol.Schema({
    vol.Required(CONF_TYPE): str,
    vol.Optional(CONF_NAME): str,
    # Specify ID if you have two auth module for same type.
    vol.Optional(CONF_ID): str,
}, extra=vol.ALLOW_EXTRA)

SESSION_EXPIRATION = timedelta(minutes=5)

DATA_REQS = 'mfa_auth_module_reqs_processed'

_LOGGER = logging.getLogger(__name__)


async def auth_mfa_module_from_config(hass, config):
    """Initialize an auth module from a config."""
    module_name = config[CONF_TYPE]
    module = await _load_mfa_module(hass, module_name)

    if module is None:
        return None

    try:
        config = module.CONFIG_SCHEMA(config)
    except vol.Invalid as err:
        _LOGGER.error('Invalid configuration for multi-factor module %s: %s',
                      module_name, humanize_error(config, err))
        return None

    return MULTI_FACTOR_AUTH_MODULES[module_name](hass, config)


async def _load_mfa_module(hass, module_name):
    """Load an mfa auth module."""
    module_path = 'homeassistant.auth.mfa_modules.{}'.format(module_name)

    try:
        module = importlib.import_module(module_path)
    except ImportError:
        _LOGGER.warning('Unable to find %s', module_path)
        return None

    if hass.config.skip_pip or not hasattr(module, 'REQUIREMENTS'):
        return module

    processed = hass.data.get(DATA_REQS)
    if processed and module_name in processed:
        return module

    hass.data[DATA_REQS] = set()

    req_success = await requirements.async_process_requirements(
        hass, module_path, module.REQUIREMENTS)

    if not req_success:
        return None

    processed.add(module_name)
    return module


class MultiFactorAuthModule:
    """Multi-factor Auth Module of validation function."""

    DEFAULT_TITLE = 'Unnamed auth module'

    def __init__(self, hass, config):
        """Initialize an auth module."""
        self.hass = hass
        self.config = config
        _LOGGER.debug('auth mfa module %s loaded.',
                      self.type if self.id is None else "{}[{}]".format(
                          self.type, self.id
                      ))

    @property
    def id(self):  # pylint: disable=invalid-name
        """Return id of the auth module.

        Default is same as type
        """
        return self.config.get(CONF_ID, self.type)

    @property
    def type(self):
        """Return type of the module."""
        return self.config[CONF_TYPE]

    @property
    def name(self):
        """Return the name of the auth module."""
        return self.config.get(CONF_NAME, self.DEFAULT_TITLE)

    @property
    def input_schema(self):
        """Return a voluptuous schema to define mfa auth module's input."""
        raise NotImplementedError

    # Implement by extending class

    async def async_setup_user(self, user_id, data=None):
        """Setup mfa auth module for user."""
        raise NotImplementedError

    async def async_depose_user(self, user_id):
        """Remove user from mfa module."""
        raise NotImplementedError

    async def async_validation(self, user_id, user_input):
        """Return True if validation passed."""
        raise NotImplementedError
