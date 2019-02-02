"""
Support for interacting with Linode nodes.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.linode/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.components.linode import (
    CONF_NODES, ATTR_CREATED, ATTR_NODE_ID, ATTR_NODE_NAME,
    ATTR_IPV4_ADDRESS, ATTR_IPV6_ADDRESS, ATTR_MEMORY,
    ATTR_REGION, ATTR_VCPUS, DATA_LINODE)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['linode']

DEFAULT_NAME = 'Node'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NODES): vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Linode Node switch."""
    linode = hass.data.get(DATA_LINODE)
    nodes = config.get(CONF_NODES)

    dev = []
    for node in nodes:
        node_id = linode.get_node_id(node)
        if node_id is None:
            _LOGGER.error("Node %s is not available", node)
            return
        dev.append(LinodeSwitch(linode, node_id))

    add_entities(dev, True)


class LinodeSwitch(SwitchDevice):
    """Representation of a Linode Node switch."""

    def __init__(self, li, node_id):
        """Initialize a new Linode sensor."""
        self._linode = li
        self._node_id = node_id
        self.data = None
        self._state = None
        self._attrs = {}
        self._name = None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Linode Node."""
        return self._attrs

    def turn_on(self, **kwargs):
        """Boot-up the Node."""
        if self.data.status != 'running':
            self.data.boot()

    def turn_off(self, **kwargs):
        """Shutdown the nodes."""
        if self.data.status == 'running':
            self.data.shutdown()

    def update(self):
        """Get the latest data from the device and update the data."""
        self._linode.update()
        if self._linode.data is not None:
            for node in self._linode.data:
                if node.id == self._node_id:
                    self.data = node
        if self.data is not None:
            self._state = self.data.status == 'running'
            self._attrs = {
                ATTR_CREATED: self.data.created,
                ATTR_NODE_ID: self.data.id,
                ATTR_NODE_NAME: self.data.label,
                ATTR_IPV4_ADDRESS: self.data.ipv4,
                ATTR_IPV6_ADDRESS: self.data.ipv6,
                ATTR_MEMORY: self.data.specs.memory,
                ATTR_REGION: self.data.region.country,
                ATTR_VCPUS: self.data.specs.vcpus,
            }
            self._name = self.data.label
