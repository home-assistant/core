"""
Support for ISY994 binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.isy994/
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable  # noqa

from homeassistant.components.binary_sensor import BinarySensorDevice, DOMAIN
import homeassistant.components.isy994 as isy
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNKNOWN
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

UOM = ['2', '78']
STATES = [STATE_OFF, STATE_ON, 'true', 'false']

ISY_DEVICE_TYPES = {
    'moisture': ['16.8', '16.13', '16.14'],
    'opening': ['16.9', '16.6', '16.7', '16.2', '16.17', '16.20', '16.21'],
    'motion': ['16.1', '16.4', '16.5', '16.3']
}


# pylint: disable=unused-argument
def setup_platform(hass, config: ConfigType,
                   add_devices: Callable[[list], None], discovery_info=None):
    """Set up the ISY994 binary sensor platform."""
    if isy.ISY is None or not isy.ISY.connected:
        _LOGGER.error("A connection has not been made to the ISY controller")
        return False

    devices = []
    devices_by_nid = {}
    child_nodes = []

    for node in isy.filter_nodes(isy.SENSOR_NODES, units=UOM,
                                 states=STATES):
        if node.parent_node is None:
            device = ISYBinarySensorDevice(node)
            devices.append(device)
            devices_by_nid[node.nid] = device
        else:
            # We'll process the child nodes last, to ensure all parent nodes
            # have been processed
            child_nodes.append(node)

    for node in child_nodes:
        try:
            devices_by_nid[node.parent_node.nid].add_child_node(node)
        except KeyError:
            _LOGGER.error("Node %s has a parent node %s, but no device "
                          "was created for the parent. Skipping.",
                          node.nid, node.parent_nid)

    for program in isy.PROGRAMS.get(DOMAIN, []):
        try:
            status = program[isy.KEY_STATUS]
        except (KeyError, AssertionError):
            pass
        else:
            devices.append(ISYBinarySensorProgram(program.name, status))

    add_devices(devices)


class ISYBinarySensorDevice(isy.ISYDevice, BinarySensorDevice):
    """Representation of an ISY994 binary sensor device.

    Often times, a single device is represented by multiple nodes in the ISY,
    allowing for different nuances in how those devices report their on and
    off events. This class turns those multiple nodes in to a single Hass
    entity and handles both ways that ISY binary sensors can work.
    """

    def __init__(self, node) -> None:
        """Initialize the ISY994 binary sensor device."""
        super().__init__(node)
        self._negative_node = None
        self._heartbeat_node = None
        self._heartbeat_timestamp = None
        self._device_class_from_type = self._detect_device_type()
        # pylint: disable=protected-access
        self._computed_state = bool(self._node.status._val)

    @asyncio.coroutine
    def async_added_to_hass(self) -> None:
        """Subscribe to the node and subnode event emitters."""
        super().async_added_to_hass()

        self._node.controlEvents.subscribe(self._positive_node_control_handler)

        try:
            self._negative_node.controlEvents.subscribe(
                self._negative_node_control_handler)
        except AttributeError:
            # Heartbeat node doesn't exist
            pass

        try:
            self._heartbeat_node.controlEvents.subscribe(
                self._heartbeat_node_control_handler)
        except AttributeError:
            # Heartbeat node doesn't exist
            pass

    def _detect_device_type(self) -> str:
        try:
            device_type = self._node.type
        except AttributeError:
            return None

        split_type = device_type.split('.')
        for device_class, ids in ISY_DEVICE_TYPES.items():
            if split_type[0] + '.' + split_type[1] in ids:
                return device_class

        return None

    def add_child_node(self, child):
        """Add a child node to this binary sensor device.

        The child node can either be a node that receives the 'off' events, or
        a heartbeat node for reporting that this device is still alive
        """
        subnode_id = int(child.nid[-1])
        if subnode_id == 2:
            # "Negative" node that can be used to represent a negative state
            # when it reports "On"
            self._negative_node = child
        elif subnode_id == 4:
            # Heartbeat node that just reports "On" every 24 hours
            self._heartbeat_timestamp = STATE_UNKNOWN
            self._heartbeat_node = child

    def _negative_node_control_handler(self, event: object) -> None:
        """Handle an "On" control event from the "negative" node."""
        if event == 'DON':
            _LOGGER.debug("Sensor %s turning Off via the Negative node "
                          "sending a DON command", self.name)
            self._computed_state = False
            self.schedule_update_ha_state()

    def _positive_node_control_handler(self, event: object) -> None:
        """Handle On and Off control event coming from the primary node.

        Depending on device configuration, sometimes only On events
        will come to this node, with the negative node representing Off
        events
        """
        if event == 'DON':
            _LOGGER.debug("Sensor %s turning On via the Primary node "
                          "sending a DON command", self.name)
            self._computed_state = True
            self.schedule_update_ha_state()
        if event == 'DOF':
            _LOGGER.debug("Sensor %s turning Off via the Primary node "
                          "sending a DOF command", self.name)
            self._computed_state = False
            self.schedule_update_ha_state()

    def _heartbeat_node_control_handler(self, event: object) -> None:
        """Update the heartbeat timestamp when an On event is sent."""
        if event == 'DON':
            self._heartbeat_timestamp = datetime.now().isoformat()
            self.schedule_update_ha_state()

    # pylint: disable=unused-argument
    def on_update(self, event: object) -> None:
        """Ignore primary node status updates.

        We listen directly to the Control events on all nodes for this
        device.
        """
        pass

    @property
    def value(self) -> bool:
        """Get the current value of the device.

        Insteon leak sensors set their primary node to On when the state is
        DRY, not WET, so we invert the binary state if the user indicates
        that it is a moisture sensor.
        """
        try:
            if self.device_class == 'moisture':
                return not self._computed_state
        except AttributeError:
            pass

        return self._computed_state

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 binary sensor device is on."""
        return self.value

    @property
    def device_class(self) -> str:
        """Return the class of this device.

        This was discovered by parsing the device type code during init
        """
        return self._device_class_from_type

    @property
    def device_state_attributes(self):
        """Get the state attributes for the device."""
        attr = super().device_state_attributes
        if self._heartbeat_timestamp is not None:
            attr['last_heartbeat'] = self._heartbeat_timestamp
        return attr


class ISYBinarySensorProgram(isy.ISYDevice, BinarySensorDevice):
    """Representation of an ISY994 binary sensor program.

    This does not need all of the subnode logic in the device version of binary
    sensors.
    """

    def __init__(self, name, node) -> None:
        """Initialize the ISY994 binary sensor program."""
        super().__init__(node)
        self._name = name

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 binary sensor device is on."""
        return bool(self.value)
