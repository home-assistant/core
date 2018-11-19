"""
Support for Zigbee Home Automation devices that should fire events.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging
from homeassistant.util import slugify
from homeassistant.core import EventOrigin, callback


_LOGGER = logging.getLogger(__name__)


async def async_setup_event(hass, discovery_info):
    """Set up events for devices that have been registered in const.py.

    Will create events for devices registered in REMOTE_DEVICE_TYPES.
    """
    from homeassistant.components.zha import configure_reporting
    out_clusters = discovery_info['out_clusters']
    in_clusters = discovery_info['in_clusters']
    events = []
    for in_cluster in in_clusters:
        event = ZHAEvent(hass, in_cluster, discovery_info)
        if discovery_info['new_join']:
            await configure_reporting(event.event_id, in_cluster, 0,
                                      False, 0, 600, 1)
        events.append(event)
    for out_cluster in out_clusters:
        event = ZHAEvent(hass, out_cluster, discovery_info)
        if discovery_info['new_join']:
            await configure_reporting(event.event_id, out_cluster, 0,
                                      False, 0, 600, 1)
            events.append(event)
    return events


class ZHAEvent():
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, hass, cluster, discovery_info):
        """Register callback that will be used for signals."""
        self._hass = hass
        self._cluster = cluster
        self._cluster.add_listener(self)
        ieee = discovery_info['endpoint'].device.ieee
        ieeetail = ''.join(['%02x' % (o, ) for o in ieee[-4:]])
        if discovery_info['manufacturer'] and discovery_info['model'] is not \
                None:
            self.event_id = "{}.{}_{}_{}{}".format(
                slugify(discovery_info['manufacturer']),
                slugify(discovery_info['model']),
                ieeetail,
                discovery_info['endpoint'].endpoint_id,
                discovery_info.get('entity_suffix', '')
            )
        else:
            self.event_id = "{}.event_{}{}".format(
                ieeetail,
                discovery_info['endpoint'].endpoint_id,
                discovery_info.get('entity_suffix', '')
            )

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        self._hass.bus.async_fire(
            'zha_' + self._cluster.server_commands.get(command_id)[0],
            {'device': self.event_id, 'args': args},
            EventOrigin.remote
        )

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates."""
        self._hass.bus.async_fire(
            'zha_attribute_updated',
            {'device': self.event_id,
             'attribute': self._cluster.attributes.get(attrid, ['Unknown'])[0],
             'attribute_id': attrid,
             'value': value},
            EventOrigin.remote
        )

    @callback
    def zdo_command(self, *args, **kwargs):
        """Log zdo commands for debugging."""
        _LOGGER.debug(
            "%s: issued zdo command %s with args: %s", self.event_id,
            args,
            kwargs
        )
