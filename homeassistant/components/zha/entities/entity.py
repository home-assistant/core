"""
Entity for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import asyncio
import logging
from random import uniform

from homeassistant.components.zha.const import (
    DATA_ZHA, DATA_ZHA_BRIDGE_ID, DOMAIN)
from homeassistant.components.zha.helpers import bind_configure_reporting
from homeassistant.core import callback
from homeassistant.helpers import entity
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)


class ZhaEntity(entity.Entity):
    """A base class for ZHA entities."""

    _domain = None  # Must be overridden by subclasses

    def __init__(self, endpoint, in_clusters, out_clusters, manufacturer,
                 model, application_listener, unique_id, new_join=False,
                 **kwargs):
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

        self._endpoint = endpoint
        self._in_clusters = in_clusters
        self._out_clusters = out_clusters
        self._new_join = new_join
        self._state = None
        self._unique_id = unique_id

        # Normally the entity itself is the listener. Sub-classes may set this
        # to a dict of cluster ID -> listener to receive messages for specific
        # clusters separately
        self._in_listeners = {}
        self._out_listeners = {}

        self._initialized = False
        self.manufacturer_code = None
        application_listener.register_entity(ieee, self)

    async def async_added_to_hass(self):
        """Handle entity addition to hass.

        It is now safe to update the entity state
        """
        for cluster_id, cluster in self._in_clusters.items():
            cluster.add_listener(self._in_listeners.get(cluster_id, self))
        for cluster_id, cluster in self._out_clusters.items():
            cluster.add_listener(self._out_listeners.get(cluster_id, self))

        self._endpoint.device.zdo.add_listener(self)

        if self._new_join:
            self.hass.async_create_task(self.async_configure())

        self._initialized = True

    async def async_configure(self):
        """Set cluster binding and attribute reporting."""
        for cluster_key, attrs in self.zcl_reporting_config.items():
            cluster = self._get_cluster_from_report_config(cluster_key)
            if cluster is None:
                continue

            manufacturer = None
            if cluster.cluster_id >= 0xfc00 and self.manufacturer_code:
                manufacturer = self.manufacturer_code

            skip_bind = False  # bind cluster only for the 1st configured attr
            for attr, details in attrs.items():
                min_report_interval, max_report_interval, change = details
                await bind_configure_reporting(
                    self.entity_id, cluster, attr,
                    min_report=min_report_interval,
                    max_report=max_report_interval,
                    reportable_change=change,
                    skip_bind=skip_bind,
                    manufacturer=manufacturer
                )
                skip_bind = True
                await asyncio.sleep(uniform(0.1, 0.5))
        _LOGGER.debug("%s: finished configuration", self.entity_id)

    def _get_cluster_from_report_config(self, cluster_key):
        """Parse an entry from zcl_reporting_config dict."""
        from zigpy.zcl import Cluster as Zcl_Cluster

        cluster = None
        if isinstance(cluster_key, Zcl_Cluster):
            cluster = cluster_key
        elif isinstance(cluster_key, str):
            cluster = getattr(self._endpoint, cluster_key, None)
        elif isinstance(cluster_key, int):
            if cluster_key in self._in_clusters:
                cluster = self._in_clusters[cluster_key]
            elif cluster_key in self._out_clusters:
                cluster = self._out_clusters[cluster_key]
        elif issubclass(cluster_key, Zcl_Cluster):
            cluster_id = cluster_key.cluster_id
            if cluster_id in self._in_clusters:
                cluster = self._in_clusters[cluster_id]
            elif cluster_id in self._out_clusters:
                cluster = self._out_clusters[cluster_id]
        return cluster

    @property
    def zcl_reporting_config(self):
        """Return a dict of ZCL attribute reporting configuration.

        {
            Cluster_Class: {
                attr_id: (min_report_interval, max_report_interval, change),
                attr_name: (min_rep_interval, max_rep_interval, change)
            }
            Cluster_Instance: {
                attr_id: (min_report_interval, max_report_interval, change),
                attr_name: (min_rep_interval, max_rep_interval, change)
            }
            cluster_id: {
                attr_id: (min_report_interval, max_report_interval, change),
                attr_name: (min_rep_interval, max_rep_interval, change)
            }
            'cluster_name': {
                attr_id: (min_report_interval, max_report_interval, change),
                attr_name: (min_rep_interval, max_rep_interval, change)
            }
        }
        """
        return {}

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._device_state_attributes

    @property
    def should_poll(self) -> bool:
        """Let ZHA handle polling."""
        return False

    @callback
    def attribute_updated(self, attribute, value):
        """Handle an attribute updated on this cluster."""
        pass

    @callback
    def zdo_command(self, tsn, command_id, args):
        """Handle a ZDO command received on this cluster."""
        pass

    @callback
    def device_announce(self, device):
        """Handle device_announce zdo event."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @callback
    def permit_duration(self, permit_duration):
        """Handle permit_duration zdo event."""
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
            'name': self._device_state_attributes.get('friendly_name', ieee),
            'via_hub': (DOMAIN, self.hass.data[DATA_ZHA][DATA_ZHA_BRIDGE_ID]),
        }

    @callback
    def zha_send_event(self, cluster, command, args):
        """Relay entity events to hass."""
        pass  # don't relay events from entities
