"""
Entity for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
from asyncio import sleep
from random import uniform
import logging

from homeassistant.components.zha.const import (
    DATA_ZHA, DATA_ZHA_BRIDGE_ID, DOMAIN)
from homeassistant.components.zha.helpers import configure_reporting
from homeassistant.core import callback
from homeassistant.helpers import entity
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)


class ZhaEntity(entity.Entity):
    """A base class for ZHA entities."""

    _domain = None  # Must be overridden by subclasses

    def __init__(self, endpoint, in_clusters, out_clusters, manufacturer,
                 model, application_listener, unique_id, **kwargs):
        """Init ZHA entity."""
        self._device_state_attributes = {}
        ieee = endpoint.device.ieee
        ieeetail = ''.join(['%02x' % (o, ) for o in ieee[-4:]])
        if manufacturer and model is not None:
            self.entity_id = "{}.{}_{}_{}_{}{}".format(
                self._domain,
                slugify(manufacturer),
                slugify(model),
                ieeetail,
                endpoint.endpoint_id,
                kwargs.get('entity_suffix', ''),
            )
            self._device_state_attributes['friendly_name'] = "{} {}".format(
                manufacturer,
                model,
            )
        else:
            self.entity_id = "{}.zha_{}_{}{}".format(
                self._domain,
                ieeetail,
                endpoint.endpoint_id,
                kwargs.get('entity_suffix', ''),
            )

        self._attributes_to_report = {}
        self._endpoint = endpoint
        self._in_clusters = in_clusters
        self._out_clusters = out_clusters
        self._state = None
        self._unique_id = unique_id

        # Normally the entity itself is the listener. Sub-classes may set this
        # to a dict of cluster ID -> listener to receive messages for specific
        # clusters separately
        self._in_listeners = {}
        self._out_listeners = {}

        self._initialized = False
        application_listener.register_entity(ieee, self)

    async def async_added_to_hass(self):
        """Handle entity addition to hass.

        It is now safe to update the entity state
        """
        for cluster_id, cluster in self._in_clusters.items():
            cluster.add_listener(self._in_listeners.get(cluster_id, self))
        for cluster_id, cluster in self._out_clusters.items():
            cluster.add_listener(self._out_listeners.get(cluster_id, self))

        self._initialized = True

    async def async_configure(self):
        """Set cluster binding and attribute reporting."""
        from zigpy.zcl import Cluster as Zcl_Cluster

        for key, attrs in self.attributes_to_report.items():
            cluster = None
            if isinstance(key, str):
                cluster = getattr(self._endpoint, key, None)
            elif isinstance(key, int):
                if key in self._in_clusters:
                    cluster = self._in_clusters[key]
                elif key in self._out_clusters:
                    cluster = self._out_clusters[key]
            elif isinstance(key, Zcl_Cluster):
                cluster = key
            elif issubclass(key, Zcl_Cluster):
                key = key.cluster_id
                if key in self._in_clusters:
                    cluster = self._in_clusters[key]
                elif key in self._out_clusters:
                    cluster = self._out_clusters[key]
            if cluster is None:
                continue

            skip_bind = False  # bind cluster only for the 1st configured attr
            for attr, details in attrs.items():
                min_report_interval, max_report_interval, change = details
                await configure_reporting(
                    self.entity_id, cluster, attr,
                    min_report=min_report_interval,
                    max_report=max_report_interval,
                    reportable_change=change,
                    skip_bind=skip_bind
                )
                skip_bind = True
                await sleep(uniform(0.1, 0.8))
        _LOGGER.debug("%s: finished configuration", self.entity_id)

    @property
    def attributes_to_report(self):
        """Return a dict of attributes to report.

        {
            cluster_id: {
                attr_id: (min_report_interval, max_report_interval, change),
                attr_name: (min_rep_interval, max_rep_interval, change)
            }
            'cluster_name': {
                attr_id: (min_report_interval, max_report_interval, change),
                attr_name: (min_rep_interval, max_rep_interval, change)
            }
            Cluster_Class: {
                attr_id: (min_report_interval, max_report_interval, change),
                attr_name: (min_rep_interval, max_rep_interval, change)
            }
        }
        """
        return self._attributes_to_report

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._device_state_attributes

    @callback
    def attribute_updated(self, attribute, value):
        """Handle an attribute updated on this cluster."""
        pass

    @callback
    def zdo_command(self, tsn, command_id, args):
        """Handle a ZDO command received on this cluster."""
        pass

    @property
    def device_info(self):
        """Return a device description for device registry."""
        ieee = str(self._endpoint.device.ieee)
        return {
            'connections': {(CONNECTION_ZIGBEE, ieee)},
            'identifiers': {(DOMAIN, ieee)},
            'manufacturer': self._endpoint.manufacturer,
            'model': self._endpoint.model,
            'name': self._device_state_attributes['friendly_name'],
            'via_hub': (DOMAIN, self.hass.data[DATA_ZHA][DATA_ZHA_BRIDGE_ID]),
        }

    @callback
    def zha_send_event(self, cluster, command, args):
        """Relay entity events to hass."""
        pass  # don't relay events from entities
