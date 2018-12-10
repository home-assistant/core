"""
Event for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

from homeassistant.core import EventOrigin, callback
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)


class ZhaEvent():
    """A base class for ZHA events."""

    def __init__(self, hass, cluster, **kwargs):
        """Init ZHA event."""
        self._hass = hass
        self._cluster = cluster
        cluster.add_listener(self)
        ieee = cluster.endpoint.device.ieee
        ieeetail = ''.join(['%02x' % (o, ) for o in ieee[-4:]])
        endpoint = cluster.endpoint
        if endpoint.manufacturer and endpoint.model is not None:
            self._unique_id = "{}.{}_{}_{}_{}{}".format(
                'zha_event',
                slugify(endpoint.manufacturer),
                slugify(endpoint.model),
                ieeetail,
                cluster.endpoint.endpoint_id,
                kwargs.get('entity_suffix', ''),
            )
        else:
            self._unique_id = "{}.zha_{}_{}{}".format(
                'zha_event',
                ieeetail,
                cluster.endpoint.endpoint_id,
                kwargs.get('entity_suffix', ''),
            )

    @callback
    def attribute_updated(self, attribute, value):
        """Handle an attribute updated on this cluster."""
        pass

    @callback
    def zdo_command(self, tsn, command_id, args):
        """Handle a ZDO command received on this cluster."""
        pass

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle a cluster command received on this cluster."""
        pass

    @callback
    def zha_send_event(self, cluster, command, args):
        """Relay entity events to hass."""
        self._hass.bus.async_fire(
            'zha_event',
            {
                'unique_id': self._unique_id,
                'command': command,
                'args': args
            },
            EventOrigin.remote
        )
