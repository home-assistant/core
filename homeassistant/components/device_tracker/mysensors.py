"""
Support for tracking MySensors devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.mysensors/
"""
import logging

import voluptuous as vol

from homeassistant.components import mysensors
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

CONF_MAX_GPS_ACCURACY = 'max_gps_accuracy'
DEPENDENCIES = ['mysensors']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAX_GPS_ACCURACY, default=0): vol.Coerce(float),
})


def setup_scanner(hass, config, see):
    """Setup the MySensors tracker."""
    def mysensors_callback(gateway, node_id):
        """Callback for mysensors platform."""
        node = gateway.sensors[node_id]
        if node.sketch_name is None:
            _LOGGER.info('No sketch_name: node %s', node_id)
            return

        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        max_gps_accuracy = config[CONF_MAX_GPS_ACCURACY]

        for child in node.children.values():
            position = child.values.get(set_req.V_POSITION)
            if child.type != pres.S_GPS or position is None:
                continue
            try:
                latitude, longitude, _ = position.split(',')
            except ValueError:
                _LOGGER.error('Payload for V_POSITION %s is not of format '
                              'latitude,longitude,altitude', position)
                continue
            name = '{} {} {}'.format(
                node.sketch_name, node_id, child.id)
            attr = {
                mysensors.ATTR_CHILD_ID: child.id,
                mysensors.ATTR_DESCRIPTION: child.description,
                mysensors.ATTR_DEVICE: gateway.device,
                mysensors.ATTR_NODE_ID: node_id,
            }
            see(
                dev_id=slugify(name),
                host_name=name,
                gps=(latitude, longitude),
                gps_accuracy=max_gps_accuracy,
                battery=node.battery_level,
                attributes=attr
            )

    gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
    if not gateways:
        return
    for gateway in gateways:
        gateway.platform_callbacks.append(mysensors_callback)

    return True
