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
STORAGE_KEY = 'auth_module.insecure_example'

_LOGGER = logging.getLogger(__name__)


@MULTI_FACTOR_AUTH_MODULES.register('insecure_example')
class InsecureExampleModule(MultiFactorAuthModule):
    """Example auth module validate pin."""

    DEFAULT_TITLE = 'Insecure Personal Identify Number'

    def __init__(self, hass, config):
        """Initialize the user data store."""
        super().__init__(hass, config)
        self._data = None
        self._users = config.get('users', [])

    @property
    def input_schema(self):
        """Input schema."""
        schema = OrderedDict()
        schema['pin'] = str
        return schema

    @property
    def users(self):
        """Return users."""
        return self._users

    async def async_setup_user(self, user_id, data=None):
        """Setup auth module for user."""
        if not data:
            raise ValueError('Expect data parameter')

        pin = data.get('pin')
        if not pin:
            raise ValueError('Expect pin in data parameter')

        for user in self._users:
            if user and user.get('user_id') == user_id:
                # already setup, override
                user['pin'] = pin
                return pin

        self._users.append({'user_id': user_id, 'pin': pin})
        return pin

    async def async_depose_user(self, user_id):
        """Depose auth module for user."""
        found = None
        for user in self._users:
            if user and user.get('user_id') == user_id:
                found = user
                break
        if found:
            self._users.remove(found)

    async def async_validation(self, user_id, user_input):
        """Return True if validation passed."""
        if user_id is None or user_input is None:
            return False

        for user in self.users:
            if user_id == user.get('user_id'):
                if user.get('pin') == user_input.get('pin'):
                    return True

        return False
