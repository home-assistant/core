"""Support for monitoring the state of Linode Nodes."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    ATTR_CREATED,
    ATTR_IPV4_ADDRESS,
    ATTR_IPV6_ADDRESS,
    ATTR_MEMORY,
    ATTR_NODE_ID,
    ATTR_NODE_NAME,
    ATTR_REGION,
    ATTR_VCPUS,
    CONF_NODES,
    DATA_LINODE,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Node"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_NODES): vol.All(cv.ensure_list, [cv.string])}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Linode droplet sensor."""
    linode = hass.data[DATA_LINODE]
    nodes = config[CONF_NODES]

    dev = []
    for node in nodes:
        if (node_id := linode.get_node_id(node)) is None:
            _LOGGER.error("Node %s is not available", node)
            return
        dev.append(LinodeBinarySensor(linode, node_id))

    add_entities(dev, True)


class LinodeBinarySensor(BinarySensorEntity):
    """Representation of a Linode droplet sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOVING

    def __init__(self, li, node_id):  # pylint: disable=invalid-name
        """Initialize a new Linode sensor."""
        self._linode = li
        self._node_id = node_id
        self._attr_extra_state_attributes = {}
        self._attr_name = None

    def update(self):
        """Update state of sensor."""
        data = None
        self._linode.update()
        if self._linode.data is not None:
            for node in self._linode.data:
                if node.id == self._node_id:
                    data = node

        if data is not None:
            self._attr_is_on = data.status == "running"
            self._attr_extra_state_attributes = {
                ATTR_CREATED: data.created,
                ATTR_NODE_ID: data.id,
                ATTR_NODE_NAME: data.label,
                ATTR_IPV4_ADDRESS: data.ipv4,
                ATTR_IPV6_ADDRESS: data.ipv6,
                ATTR_MEMORY: data.specs.memory,
                ATTR_REGION: data.region.country,
                ATTR_VCPUS: data.specs.vcpus,
            }
            self._attr_name = data.label
