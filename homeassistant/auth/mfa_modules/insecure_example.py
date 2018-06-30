"""Example auth module."""
import logging

import voluptuous as vol

from . import MultiFactorAuthModule, MULTI_FACTOR_AUTH_MODULES, \
    MULTI_FACTOR_AUTH_MODULE_SCHEMA

CONFIG_SCHEMA = MULTI_FACTOR_AUTH_MODULE_SCHEMA.extend({
    vol.Required('data'): [vol.Schema({
        vol.Required('user_id'): str,
        vol.Required('pin'): str,
    })]
}, extra=vol.PREVENT_EXTRA)

_LOGGER = logging.getLogger(__name__)


@MULTI_FACTOR_AUTH_MODULES.register('insecure_example')
class InsecureExampleModule(MultiFactorAuthModule):
    """Example auth module validate pin."""

    DEFAULT_TITLE = 'Insecure Personal Identify Number'

    def __init__(self, hass, config):
        """Initialize the user data store."""
        super().__init__(hass, config)
        self._data = config['data']

    @property
    def input_schema(self):
        """Validate login flow input data."""
        return vol.Schema({'pin': str})

    @property
    def setup_schema(self):
        """Validate async_setup_user input data."""
        return vol.Schema({'pin': str})

    async def async_setup_user(self, user_id, setup_data):
        """Set up user to use mfa module."""
        # data shall has been validate in caller
        pin = setup_data['pin']

        for data in self._data:
            if data['user_id'] == user_id:
                # already setup, override
                data['pin'] = pin
                return

        self._data.append({'user_id': user_id, 'pin': pin})

    async def async_depose_user(self, user_id):
        """Remove user from mfa module."""
        found = None
        for data in self._data:
            if data['user_id'] == user_id:
                found = data
                break
        if found:
            self._data.remove(found)

    async def async_is_user_setup(self, user_id):
        """Return whether user is setup."""
        for data in self._data:
            if data['user_id'] == user_id:
                return True
        return False

    async def async_validation(self, user_id, user_input):
        """Return True if validation passed."""
        for data in self._data:
            if data['user_id'] == user_id:
                # user_input has been validate in caller
                if data['pin'] == user_input['pin']:
                    return True

        return False
