"""
This component provides support for RainMachine sprinkler controllers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainmachine/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL,
    CONF_SWITCHES)
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['regenmaschine==0.4.1']

_LOGGER = logging.getLogger(__name__)

DATA_RAINMACHINE = 'data_rainmachine'
DOMAIN = 'rainmachine'

NOTIFICATION_ID = 'rainmachine_notification'
NOTIFICATION_TITLE = 'RainMachine Component Setup'

CONF_ZONE_RUN_TIME = 'zone_run_time'

DEFAULT_ATTRIBUTION = 'Data provided by Green Electronics LLC'
DEFAULT_ICON = 'mdi:water'
DEFAULT_PORT = 8080
DEFAULT_SSL = True

PROGRAM_UPDATE_TOPIC = '{0}_program_update'.format(DOMAIN)

SWITCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_ZONE_RUN_TIME):
        cv.positive_int
})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_IP_ADDRESS): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_SWITCHES): SWITCH_SCHEMA,
        })
    },
    extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the RainMachine component."""
    from regenmaschine import Authenticator, Client
    from regenmaschine.exceptions import HTTPError
    from requests.exceptions import ConnectTimeout

    conf = config[DOMAIN]
    ip_address = conf[CONF_IP_ADDRESS]
    password = conf[CONF_PASSWORD]
    port = conf[CONF_PORT]
    ssl = conf[CONF_SSL]

    _LOGGER.debug('Setting up RainMachine client')

    try:
        auth = Authenticator.create_local(
            ip_address, password, port=port, https=ssl)
        client = Client(auth)
        hass.data[DATA_RAINMACHINE] = RainMachine(client)
    except (HTTPError, ConnectTimeout, UnboundLocalError) as exc_info:
        _LOGGER.error('An error occurred: %s', str(exc_info))
        hass.components.persistent_notification.create(
            'Error: {0}<br />'
            'You will need to restart hass after fixing.'
            ''.format(exc_info),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    _LOGGER.debug('Setting up switch platform')
    switch_config = conf.get(CONF_SWITCHES, {})
    discovery.load_platform(hass, 'switch', DOMAIN, switch_config, config)

    _LOGGER.debug('Setup complete')

    return True


class RainMachine(object):
    """Define a generic RainMachine object."""

    def __init__(self, client):
        """Initialize."""
        self.client = client
        self.device_mac = self.client.provision.wifi()['macAddress']


class RainMachineEntity(Entity):
    """Define a generic RainMachine entity."""

    def __init__(self,
                 rainmachine,
                 rainmachine_type,
                 rainmachine_entity_id,
                 icon=DEFAULT_ICON):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._icon = icon
        self._rainmachine_type = rainmachine_type
        self._rainmachine_entity_id = rainmachine_entity_id
        self.rainmachine = rainmachine

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_{1}_{2}'.format(
            self.rainmachine.device_mac.replace(
                ':', ''), self._rainmachine_type,
            self._rainmachine_entity_id)
