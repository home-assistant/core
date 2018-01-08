"""Entity class that represents Z-Wave node."""
import logging

from homeassistant.core import callback
from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_WAKEUP, ATTR_ENTITY_ID
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import (
    ATTR_NODE_ID, COMMAND_CLASS_WAKE_UP, ATTR_SCENE_ID, ATTR_SCENE_DATA,
    ATTR_BASIC_LEVEL, EVENT_NODE_EVENT, EVENT_SCENE_ACTIVATED, DOMAIN,
    COMMAND_CLASS_CENTRAL_SCENE)
from .util import node_name

_LOGGER = logging.getLogger(__name__)

ATTR_QUERY_STAGE = 'query_stage'
ATTR_AWAKE = 'is_awake'
ATTR_READY = 'is_ready'
ATTR_FAILED = 'is_failed'
ATTR_PRODUCT_NAME = 'product_name'
ATTR_MANUFACTURER_NAME = 'manufacturer_name'
ATTR_NODE_NAME = 'node_name'

STAGE_COMPLETE = 'Complete'

_REQUIRED_ATTRIBUTES = [
    ATTR_QUERY_STAGE, ATTR_AWAKE, ATTR_READY, ATTR_FAILED,
    'is_info_received', 'max_baud_rate', 'is_zwave_plus']
_OPTIONAL_ATTRIBUTES = ['capabilities', 'neighbors', 'location']
_COMM_ATTRIBUTES = [
    'sentCnt', 'sentFailed', 'retries', 'receivedCnt', 'receivedDups',
    'receivedUnsolicited', 'sentTS', 'receivedTS', 'lastRequestRTT',
    'averageRequestRTT', 'lastResponseRTT', 'averageResponseRTT']
ATTRIBUTES = _REQUIRED_ATTRIBUTES + _OPTIONAL_ATTRIBUTES


class ZWaveBaseEntity(Entity):
    """Base class for Z-Wave Node and Value entities."""

    def __init__(self):
        """Initialize the base Z-Wave class."""
        self._update_scheduled = False
        self.old_entity_id = None
        self.new_entity_id = None

    def maybe_schedule_update(self):
        """Maybe schedule state update.

        If value changed after device was created but before setup_platform
        was called - skip updating state.
        """
        if self.hass and not self._update_scheduled:
            self.hass.add_job(self._schedule_update)

    @callback
    def _schedule_update(self):
        """Schedule delayed update."""
        if self._update_scheduled:
            return

        @callback
        def do_update():
            """Really update."""
            self.hass.async_add_job(self.async_update_ha_state)
            self._update_scheduled = False

        self._update_scheduled = True
        self.hass.loop.call_later(0.1, do_update)


class ZWaveNodeEntity(ZWaveBaseEntity):
    """Representation of a Z-Wave node."""

    def __init__(self, node, network, new_entity_ids):
        """Initialize node."""
        # pylint: disable=import-error
        super().__init__()
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        self._network = network
        self.node = node
        self.node_id = self.node.node_id
        self._name = node_name(self.node)
        self._product_name = node.product_name
        self._manufacturer_name = node.manufacturer_name
        self.old_entity_id = "{}.{}_{}".format(
            DOMAIN, slugify(self._name), self.node_id)
        self.new_entity_id = "{}.{}".format(DOMAIN, slugify(self._name))
        if not new_entity_ids:
            self.entity_id = self.old_entity_id
        self._attributes = {}
        self.wakeup_interval = None
        self.location = None
        self.battery_level = None
        dispatcher.connect(
            self.network_node_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)
        dispatcher.connect(self.network_node_changed, ZWaveNetwork.SIGNAL_NODE)
        dispatcher.connect(
            self.network_node_changed, ZWaveNetwork.SIGNAL_NOTIFICATION)
        dispatcher.connect(
            self.network_node_event, ZWaveNetwork.SIGNAL_NODE_EVENT)
        dispatcher.connect(
            self.network_scene_activated, ZWaveNetwork.SIGNAL_SCENE_EVENT)

    def network_node_changed(self, node=None, value=None, args=None):
        """Handle a changed node on the network."""
        if node and node.node_id != self.node_id:
            return
        if args is not None and 'nodeId' in args and \
                args['nodeId'] != self.node_id:
            return

        # Process central scene activation
        if (value is not None and
                value.command_class == COMMAND_CLASS_CENTRAL_SCENE):
            self.central_scene_activated(value.index, value.data)

        self.node_changed()

    def get_node_statistics(self):
        """Retrieve statistics from the node."""
        return self._network.manager.getNodeStatistics(
            self._network.home_id, self.node_id)

    def node_changed(self):
        """Update node properties."""
        attributes = {}
        stats = self.get_node_statistics()
        for attr in ATTRIBUTES:
            value = getattr(self.node, attr)
            if attr in _REQUIRED_ATTRIBUTES or value:
                attributes[attr] = value

        for attr in _COMM_ATTRIBUTES:
            attributes[attr] = stats[attr]

        if self.node.can_wake_up():
            for value in self.node.get_values(COMMAND_CLASS_WAKE_UP).values():
                if value.index != 0:
                    continue

                self.wakeup_interval = value.data
                break
        else:
            self.wakeup_interval = None

        self.battery_level = self.node.get_battery_level()
        self._attributes = attributes

        self.maybe_schedule_update()

    def network_node_event(self, node, value):
        """Handle a node activated event on the network."""
        if node.node_id == self.node.node_id:
            self.node_event(value)

    def node_event(self, value):
        """Handle a node activated event for this node."""
        if self.hass is None:
            return

        self.hass.bus.fire(EVENT_NODE_EVENT, {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_NODE_ID: self.node.node_id,
            ATTR_BASIC_LEVEL: value
        })

    def network_scene_activated(self, node, scene_id):
        """Handle a scene activated event on the network."""
        if node.node_id == self.node.node_id:
            self.scene_activated(scene_id)

    def scene_activated(self, scene_id):
        """Handle an activated scene for this node."""
        if self.hass is None:
            return

        self.hass.bus.fire(EVENT_SCENE_ACTIVATED, {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_NODE_ID: self.node.node_id,
            ATTR_SCENE_ID: scene_id
        })

    def central_scene_activated(self, scene_id, scene_data):
        """Handle an activated central scene for this node."""
        if self.hass is None:
            return

        self.hass.bus.fire(EVENT_SCENE_ACTIVATED, {
            ATTR_ENTITY_ID:   self.entity_id,
            ATTR_NODE_ID:     self.node_id,
            ATTR_SCENE_ID:    scene_id,
            ATTR_SCENE_DATA:  scene_data
        })

    @property
    def state(self):
        """Return the state."""
        if ATTR_READY not in self._attributes:
            return None

        if self._attributes[ATTR_FAILED]:
            return 'dead'
        if self._attributes[ATTR_QUERY_STAGE] != 'Complete':
            return 'initializing'
        if not self._attributes[ATTR_AWAKE]:
            return 'sleeping'
        if self._attributes[ATTR_READY]:
            return 'ready'

        return None

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attrs = {
            ATTR_NODE_ID: self.node_id,
            ATTR_NODE_NAME: self._name,
            ATTR_MANUFACTURER_NAME: self._manufacturer_name,
            ATTR_PRODUCT_NAME: self._product_name,
            'old_entity_id': self.old_entity_id,
            'new_entity_id': self.new_entity_id,
        }
        attrs.update(self._attributes)
        if self.battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = self.battery_level
        if self.wakeup_interval is not None:
            attrs[ATTR_WAKEUP] = self.wakeup_interval

        return attrs
