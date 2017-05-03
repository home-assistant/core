"""
Support for tracking MySensors devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.mysensors/
"""
import logging

from homeassistant.components import mysensors
from homeassistant.util import slugify

DEPENDENCIES = ['mysensors']

_LOGGER = logging.getLogger(__name__)


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the MySensors tracker."""
    def mysensors_callback(gateway, msg):
        """Set up callback for mysensors platform."""
        node = gateway.sensors[msg.node_id]
        if node.sketch_name is None:
            _LOGGER.debug("No sketch_name: node %s", msg.node_id)
            return

        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq

        child = node.children.get(msg.child_id)
        if child is None:
            return
        position = child.values.get(set_req.V_POSITION)
        if child.type != pres.S_GPS or position is None:
            return
        try:
            latitude, longitude, _ = position.split(',')
        except ValueError:
            _LOGGER.error("Payload for V_POSITION %s is not of format "
                          "latitude, longitude, altitude", position)
            return
        name = '{} {} {}'.format(
            node.sketch_name, msg.node_id, child.id)
        attr = {
            mysensors.ATTR_CHILD_ID: child.id,
            mysensors.ATTR_DESCRIPTION: child.description,
            mysensors.ATTR_DEVICE: gateway.device,
            mysensors.ATTR_NODE_ID: msg.node_id,
        }
        see(
            dev_id=slugify(name),
            host_name=name,
            gps=(latitude, longitude),
            battery=node.battery_level,
            attributes=attr
        )

    gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)

    for gateway in gateways:
        if float(gateway.protocol_version) < 2.0:
            continue
        gateway.platform_callbacks.append(mysensors_callback)

    return True
