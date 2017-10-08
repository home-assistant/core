"""Component to interact with Remember The Milk.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/remember_the_milk/

Minimum viable product, it currently only support creating new tasks in your
Remember The Milk (https://www.rememberthemilk.com/) account.

Ideas for improvement:
- add interface to resolve tasks
- add option to add a task to a certain list
- add option to list tasks stored in RTM
- make registration dialog nicer
"""
import logging
import os
import json
import voluptuous as vol
from homeassistant.const import (CONF_API_KEY, STATE_OK)
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['RtmAPI==0.7.0', 'httplib2==0.10.3']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'remember_the_milk'
DEFAULT_NAME = DOMAIN
GROUP_NAME_RTM = 'remember the milk accounts'

CONF_SHARED_SECRET = 'shared_secret'

RTM_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SHARED_SECRET): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        cv.string: RTM_SCHEMA
    }
}, extra=vol.ALLOW_EXTRA)

CONFIG_TOKEN = 'token'
CONFIG_FILE_NAME = 'remember_the_milk.conf'
_CONFIGURING = dict()

SERVICE_DESCRIPTION_CREATE_TASK = {
    'description': 'Create a new task in your Remember The Milk account',
    'fields': {
        'name': {
            'description': 'name of the new task, you can use the smart '
                           'syntax here',
            'example': 'do this ^today #from_hass',
        },
        # 'list_id': {
        #     'description': 'Name of the list to which the task shall be '
        #                    'added (optional). If no list_id is set, '
        #                    'the task is added to the Inbox',
        #     'example': 'some_list',
        # }
    }
}

SERVICE_SCHEMA_CREATE_TASK = vol.Schema({
    vol.Required('name'): cv.string,
    # vol.Optional('list_id'): cv.string,
})


def setup(hass, config):
    """Set up the Plant component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass,
                                group_name=GROUP_NAME_RTM)

    stored_rtm_config = RememberTheMilkConfiguration()
    for account_name, rtm_config in config[DOMAIN].items():
        _LOGGER.info("Adding Remember the milk account %s", account_name)
        api_key = rtm_config[CONF_API_KEY]
        shared_secret = rtm_config[CONF_SHARED_SECRET]
        token = stored_rtm_config.get_token(account_name)
        if token:
            _LOGGER.debug("found token for account %s", account_name)
            _create_instance(
                hass, account_name, api_key, shared_secret, token,
                stored_rtm_config, component)
        else:
            _register_new_account(
                hass, account_name, api_key, shared_secret,
                stored_rtm_config, component)

    _LOGGER.debug("Finished adding all Remember the milk accounts")
    return True


def _create_instance(hass, account_name, api_key, shared_secret,
                     token, stored_rtm_config, component):
    entity = RememberTheMilk(account_name, api_key, shared_secret,
                             token, stored_rtm_config)
    component.add_entity(entity)
    hass.services.async_register(
        DOMAIN, 'create_task', entity.create_task,
        description=SERVICE_DESCRIPTION_CREATE_TASK,
        schema=SERVICE_SCHEMA_CREATE_TASK)


def _register_new_account(hass, account_name, api_key, shared_secret,
                          stored_rtm_config, component):
    from rtmapi import Rtm

    configurator = hass.components.configurator
    api = Rtm(api_key, shared_secret, "write", None)
    url, frob = api.authenticate_desktop()
    _LOGGER.debug('sent authentication request to server')

    def register_account_callback(_):
        """Callback for configurator."""
        api.retrieve_token(frob)
        token = api.token
        if api.token is None:
            _LOGGER.error('Failed to register, please try again.')
            configurator.notify_errors(
                _CONFIGURING[account_name],
                'Failed to register, please try again.')
            return
        else:
            stored_rtm_config.set_token(account_name, token)
            _LOGGER.debug('retrieved new token from server')

            _create_instance(
                hass, account_name, api_key, shared_secret, token,
                stored_rtm_config, component)

            configurator.request_done(_CONFIGURING[account_name])
            _CONFIGURING.pop(account_name)

    _CONFIGURING[account_name] = configurator.async_request_config(
        '{} - {}'.format(DOMAIN, account_name),
        callback=register_account_callback,
        description='You need to log in to Remember The Milk to' +
        'connect your account. \n\n' +
        'Step 1: Click on the link "Remember The Milk login"\n\n' +
        'Step 2: Click on "login completed"',
        link_name='Remember The Milk login',
        link_url=url,
        submit_caption="login completed",
    )


class RememberTheMilkConfiguration(object):
    """Internal configuration data for RememberTheMilk class.

    This class stores the authentication token it get from the backend.
    """

    def __init__(self):
        """Create new instance of configuration."""
        if os.path.isfile(CONFIG_FILE_NAME):
            try:
                _LOGGER.debug('loading configuration from file: %s',
                              os.path.abspath(CONFIG_FILE_NAME))
                with open(CONFIG_FILE_NAME, 'r') as config_file:
                    self._config = json.load(config_file)
            except json.decoder.JSONDecodeError:
                _LOGGER.error('failed to load configuration file, creating a '
                              'new one: %s', os.path.abspath(CONFIG_FILE_NAME))
                self._config = dict()
        else:
            self._config = dict()

    def save_config(self):
        """Write the configuration to a file."""
        with open(CONFIG_FILE_NAME, 'w') as config_file:
            json.dump(self._config, config_file)

    def get_token(self, profile_name):
        """Get the server token for a profile."""
        if profile_name in self._config:
            return self._config[profile_name][CONFIG_TOKEN]
        return None

    def set_token(self, profile_name, token):
        """Store a new server token for a profile."""
        if profile_name not in self._config:
            self._config[profile_name] = dict()
        self._config[profile_name][CONFIG_TOKEN] = token
        self.save_config()

    def delete_token(self, profile_name):
        """Delete a token for a profile.

        Usually called when the token has expired.
        """
        self._config.pop(profile_name, None)
        self.save_config()


class RememberTheMilk(Entity):
    """MVP implementation of an interface to Remember The Milk."""

    def __init__(self, name, api_key, shared_secret, token, rtm_config):
        """Create new instance of Remember The Milk component."""
        import rtmapi

        self._name = name
        self._api_key = api_key
        self._shared_secret = shared_secret
        self._token = token
        self._rtm_config = rtm_config
        self._rtm_api = rtmapi.Rtm(api_key, shared_secret, "delete", token)
        self._token_valid = None
        self._check_token()
        _LOGGER.debug("instance created for account %s", self._name)

    def _check_token(self):
        """Check if the API token is still valid.

        If it is not valid any more, delete it from the configuration. This
        will trigger a new authentication process.
        """
        valid = self._rtm_api.token_valid()
        if not valid:
            _LOGGER.error('Token for account %s is invalid. You need to '
                          'register again!', self.name)
            self._rtm_config.delete_token(self._name)
            self._token_valid = False
        else:
            self._token_valid = True
        return self._token_valid

    def create_task(self, call):
        """Create a new task on Remember The Milk.

        You can use the smart syntax to define the attribues of a new task,
        e.g. "my task #some_tag ^today" will add tag "some_tag" and set the
        due date to today.
        """
        import rtmapi

        try:
            task_name = call.data.get('name')
            result = self._rtm_api.rtm.timelines.create()
            timeline = result.timeline.value
            self._rtm_api.rtm.tasks.add(
                timeline=timeline, name=task_name, parse='1')
            _LOGGER.info('created new task "%s" in account %s', task_name,
                         self.name)
        except rtmapi.RtmRequestFailedException as rtm_exception:
            _LOGGER.error(str(rtm_exception))
            return False
        _LOGGER.debug('added task %s', task_name)
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if not self._token_valid:
            return 'API token invalid'
        else:
            return STATE_OK
