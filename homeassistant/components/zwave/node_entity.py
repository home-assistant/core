"""Entity class that represents Z-Wave node."""
import logging

from homeassistant.core import callback
from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_WAKEUP
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import ATTR_NODE_ID, DOMAIN, COMMAND_CLASS_WAKE_UP
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


def sub_status(status, stage):
    """Format sub-status."""
    return '{} ({})'.format(status, stage) if stage else status


class ZWaveNodeEntity(ZWaveBaseEntity):
    """Representation of a Z-Wave node."""

    def __init__(self, node, network):
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
        self.entity_id = "{}.{}_{}".format(
            DOMAIN, slugify(self._name), self.node_id)
        self._attributes = {}
        self.wakeup_interval = None
        self.location = None
        self.battery_level = None
        dispatcher.connect(
            self.network_node_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)
        dispatcher.connect(self.network_node_changed, ZWaveNetwork.SIGNAL_NODE)
        dispatcher.connect(
            self.network_node_changed, ZWaveNetwork.SIGNAL_NOTIFICATION)

    def network_node_changed(self, node=None, args=None):
        """Handle a changed node on the network."""
        if node and node.node_id != self.node_id:
            return
        if args is not None and 'nodeId' in args and \
                args['nodeId'] != self.node_id:
            return
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
                self.wakeup_interval = value.data
                break
        else:
            self.wakeup_interval = None

        self.battery_level = self.node.get_battery_level()
        self._attributes = attributes

        self.maybe_schedule_update()

    @property
    def state(self):
        """Return the state."""
        if ATTR_READY not in self._attributes:
            return None
        stage = ''
        if not self._attributes[ATTR_READY]:
            # If node is not ready use stage as sub-status.
            stage = self._attributes[ATTR_QUERY_STAGE]
        if self._attributes[ATTR_FAILED]:
            return sub_status('Dead', stage)
        if not self._attributes[ATTR_AWAKE]:
            return sub_status('Sleeping', stage)
        if self._attributes[ATTR_READY]:
            return sub_status('Ready', stage)
        return stage

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
        }
        attrs.update(self._attributes)
        if self.battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = self.battery_level
        if self.wakeup_interval is not None:
            attrs[ATTR_WAKEUP] = self.wakeup_interval

        return attrs
