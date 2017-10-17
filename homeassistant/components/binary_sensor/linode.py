"""
Support for monitoring the state of Digital Ocean droplets.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.linode/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.linode import (
    CONF_NODES, ATTR_CREATED, ATTR_NODE_ID, ATTR_NODE_NAME,
    ATTR_IPV4_ADDRESS, ATTR_IPV6_ADDRESS, ATTR_MEMORY,
    ATTR_REGION, ATTR_VCPUS, DATA_LINODE)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'LiNode'
DEFAULT_DEVICE_CLASS = 'moving'
DEPENDENCIES = ['linode']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NODES): vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Linode droplet sensor."""
    linode = hass.data.get(DATA_LINODE)
    if not linode:
        return False

    nodes = config.get(CONF_NODES)

    dev = []
    for node in nodes:
        node_id = linode.get_node_id(node)
        if node_id is None:
            _LOGGER.error("Node %s is not available", node)
            return False
        dev.append(LinodeBinarySensor(node, node_id))

    add_devices(dev, True)


class LinodeBinarySensor(BinarySensorDevice):
    """Representation of a Linode droplet sensor."""

    def __init__(self, do, node_id):
        """Initialize a new Linode sensor."""
        self._linode = do
        self._node_id = node_id
        self._state = None
        self.data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.data.name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.data.status == 'active'

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEFAULT_DEVICE_CLASS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Linode Node."""
        return {
            ATTR_CREATED: self.data.created,
            ATTR_NODE_ID: self.data.id,
            ATTR_NODE_NAME: self.data.label,
            ATTR_IPV4_ADDRESS: self.data.ipv4,
            ATTR_IPV6_ADDRESS: self.data.ipv6,
            ATTR_MEMORY: self.data.specs.memory,
            ATTR_REGION: self.data.region.country,
            ATTR_VCPUS: self.data.specs.vcpus,
        }

    def update(self):
        """Update state of sensor."""
        self._linode.update()

        for node in self._linode.data:
            if node.id == self._node_id:
                self.data = node
