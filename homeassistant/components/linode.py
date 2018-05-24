"""
Support for Linode.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/linode/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['linode-api==4.1.9b1']

_LOGGER = logging.getLogger(__name__)

ATTR_CREATED = 'created'
ATTR_NODE_ID = 'node_id'
ATTR_NODE_NAME = 'node_name'
ATTR_IPV4_ADDRESS = 'ipv4_address'
ATTR_IPV6_ADDRESS = 'ipv6_address'
ATTR_MEMORY = 'memory'
ATTR_REGION = 'region'
ATTR_VCPUS = 'vcpus'

CONF_NODES = 'nodes'

DATA_LINODE = 'data_li'
LINODE_PLATFORMS = ['binary_sensor', 'switch']
DOMAIN = 'linode'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Linode component."""
    import linode

    conf = config[DOMAIN]
    access_token = conf.get(CONF_ACCESS_TOKEN)

    _linode = Linode(access_token)

    try:
        _LOGGER.info("Linode Profile %s",
                     _linode.manager.get_profile().username)
    except linode.errors.ApiError as _ex:
        _LOGGER.error(_ex)
        return False

    hass.data[DATA_LINODE] = _linode

    return True


class Linode(object):
    """Handle all communication with the Linode API."""

    def __init__(self, access_token):
        """Initialize the Linode connection."""
        import linode

        self._access_token = access_token
        self.data = None
        self.manager = linode.LinodeClient(token=self._access_token)

    def get_node_id(self, node_name):
        """Get the status of a Linode Instance."""
        import linode
        node_id = None

        try:
            all_nodes = self.manager.linode.get_instances()
            for node in all_nodes:
                if node_name == node.label:
                    node_id = node.id
        except linode.errors.ApiError as _ex:
            _LOGGER.error(_ex)

        return node_id

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Use the data from Linode API."""
        import linode
        try:
            self.data = self.manager.linode.get_instances()
        except linode.errors.ApiError as _ex:
            _LOGGER.error(_ex)
