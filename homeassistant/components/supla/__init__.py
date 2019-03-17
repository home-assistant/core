"""
Support for the Supla devices.

For more details about this platform, please refer to the documentation.
https://home-assistant.io/components/supla/
"""

import logging
from typing import Optional
import voluptuous as vol

from homeassistant.const import (
    CONF_ACCESS_TOKEN
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity import Entity


REQUIREMENTS = ['pysupla==0.0.1']


_LOGGER = logging.getLogger(__name__)
DOMAIN = 'supla'

CONF_SERVER = 'server'
CONF_SERVERS = 'servers'

SUPLA_FUNCTION_HA_CMP_MAP = {
    'CONTROLLINGTHEROLLERSHUTTER': 'cover'
}
SUPLA_CHANNELS = 'supla_channels'
SUPLA_SERVERS = 'supla_servers'


SERVER_CONFIG = vol.Schema({
    vol.Required(CONF_SERVER): cv.string,
    vol.Required(CONF_ACCESS_TOKEN): cv.string
}, extra=vol.ALLOW_EXTRA)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_SERVERS):
            vol.All(cv.ensure_list, [SERVER_CONFIG])
    })
}, extra=vol.ALLOW_EXTRA)


def discover_devices(hass, hass_config):
    """
    Run peridoically to discover new devices;
    currently it's only run at startup.
    """
    component_configs = {}

    for server_name, server in hass.data[SUPLA_SERVERS].items():

        for channel in server.get_channels(include=['iodevice']):
            channel_function = channel['function']['name']
            component_name = SUPLA_FUNCTION_HA_CMP_MAP.get(channel_function)

            if component_name is None:
                _LOGGER.warning(
                    'Unsupported function: %s, channel id: %s',
                    channel_function, channel['id']
                )
                continue

            channel['server_name'] = server_name
            component_configs.setdefault(component_name, []).append(channel)

    # Load discovered devices
    for component_name, channel in component_configs.items():
        load_platform(
            hass,
            component_name,
            'supla',
            channel,
            hass_config
        )


def setup(hass, base_config):
    """Set up the Supla component."""
    from pysupla import SuplaAPI

    server_confs = base_config[DOMAIN][CONF_SERVERS]

    hass.data[SUPLA_SERVERS] = {}
    hass.data[SUPLA_CHANNELS] = {}

    for server_conf in server_confs:
        server = SuplaAPI(
            server_conf[CONF_SERVER],
            server_conf[CONF_ACCESS_TOKEN]
        )
        hass.data[SUPLA_SERVERS][server_conf[CONF_SERVER]] = server

    discover_devices(hass, base_config)

    return True


class SuplaChannel(Entity):
    '''
    Base class of a Supla Channel (an equivalent of HA's Entity)
    '''

    def __init__(self, channel_data):
        self.server_name = channel_data['server_name']
        self.channel_data = channel_data

    @property
    def server(self):
        """
        Return PySupla's server component associated with entity
        """
        return self.hass.data[SUPLA_SERVERS][self.server_name]

    @property
    def hidden(self) -> bool:
        """Return True if the entity should be hidden from UIs."""
        return self.channel_data['hidden']

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return 'supla_{}_{}'.format(self.server_name, self.channel_data['id'])

    @property
    def name(self) -> Optional[str]:
        """Return the name of the device."""
        return self.channel_data['caption']

    @property
    def should_poll(self):
        "Supla's web API requires polling"
        return True

    def action(self, action, **add_pars):
        """
        Runs server action; actions are currently hardoced in components
        Supla's API enables autodiscovery
        """
        _LOGGER.debug(
            'Executing action %s on channel %d, params: %s',
            action,
            self.channel_data['id'],
            add_pars
        )
        self.server.execute_action(self.channel_data['id'], action, **add_pars)
        self.update()

    def update(self):
        """Call to update state."""
        self.channel_data = self.server.get_channel(
            self.channel_data['id'],
            include=['connected', 'state']
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        return attr
