"""Example auth module."""
import logging
from collections import OrderedDict

import voluptuous as vol

from . import MultiFactorAuthModule, MULTI_FACTOR_AUTH_MODULES, \
    MULTI_FACTOR_AUTH_MODULE_SCHEMA

CONFIG_SCHEMA = MULTI_FACTOR_AUTH_MODULE_SCHEMA.extend({
    vol.Required('users'): [vol.Schema({
        vol.Required('user_id'): str,
        vol.Required('pin'): str,
    })]
}, extra=vol.PREVENT_EXTRA)

STORAGE_VERSION = 1
STORAGE_KEY = 'mfa_modules.insecure_example'

_LOGGER = logging.getLogger(__name__)


@MULTI_FACTOR_AUTH_MODULES.register('insecure_example')
class InsecureExampleModule(MultiFactorAuthModule):
    """Example auth module validate pin."""

    DEFAULT_TITLE = 'Insecure Personal Identify Number'

    def __init__(self, hass, config):
        """Initialize the user data store."""
        super().__init__(hass, config)
        self._data = None
        self._users = config['users']

    @property
    def input_schema(self):
        """Validate login flow input data."""
        schema = OrderedDict()
        schema['pin'] = str
        return vol.Schema(schema)

    @property
    def setup_schema(self):
        """Validate async_setup_user input data."""
        schema = OrderedDict()
        schema['pin'] = str
        return vol.Schema(schema)

    async def async_setup_user(self, user_id, data=None):
        """Setup mfa module for user."""
        try:
            data = self.setup_schema(data)  # pylint: disable=not-callable
        except vol.Invalid as err:
            raise ValueError('Data does not match schema: {}'.format(err))

        pin = data['pin']

        for user in self._users:
            if user and user.get('user_id') == user_id:
                # already setup, override
                user['pin'] = pin
                return

        self._users.append({'user_id': user_id, 'pin': pin})

    async def async_depose_user(self, user_id):
        """Remove user from mfa module."""
        found = None
        for user in self._users:
            if user and user.get('user_id') == user_id:
                found = user
                break
        if found:
            self._users.remove(found)

    async def async_validation(self, user_id, user_input):
        """Return True if validation passed."""
        for user in self._users:
            if user_id == user.get('user_id'):
                # user_input has been validate in caller
                if user.get('pin') == user_input['pin']:
                    return True

        return False
