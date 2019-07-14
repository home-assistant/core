"""Support for ISY994 binary sensors."""
from datetime import timedelta
import logging
from typing import Callable, Optional

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from homeassistant.const import (
    CONF_DEVICE_CLASS, CONF_ICON, CONF_ID, CONF_NAME, CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON, CONF_TYPE, STATE_OFF, STATE_ON)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType, Dict
from homeassistant.util import dt as dt_util

from . import ISYDevice
from .const import (
    ISY994_NODES, ISY994_PROGRAMS, ISY994_VARIABLES, ISY_BIN_SENS_DEVICE_TYPES,
    ZWAVE_BIN_SENS_DEVICE_TYPES)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config: ConfigType,
                   add_entities: Callable[[list], None], discovery_info=None):
    """Set up the ISY994 binary sensor platform."""
    devices = []
    devices_by_nid = {}
    child_nodes = []

    for node in hass.data[ISY994_NODES][DOMAIN]:
        device_class, device_type = _detect_device_type(node)
        if node.parent_node is None or node.nid[0] in ['Z', 'n']:
            device = ISYBinarySensorDevice(node, device_class)
            devices.append(device)
            devices_by_nid[node.nid] = device
        else:
            # We'll process the Insteon child nodes last, to ensure all parent
            # nodes have been processed
            child_nodes.append((node, device_class, device_type))

    # Handle some special child node cases for Insteon Devices
    for (node, device_class, device_type) in child_nodes:
        subnode_id = int(node.nid[-1], 16)
        if device_class != 'climate':
            try:
                parent_device = devices_by_nid[node.parent_node.nid]
            except KeyError:
                _LOGGER.error("Node %s has a parent node %s, but no device "
                              "was created for the parent. Skipping.",
                              node.nid, node.parent_nid)
            else:
                subnode_id = int(node.nid[-1], 16)
                if device_class in ('opening', 'moisture'):

                    # These sensors use an optional "negative" subnode 2 to
                    # snag all state changes
                    if subnode_id == 2:
                        parent_device.add_negative_node(node)
                    elif subnode_id == 4:
                        # Subnode 4 is the heartbeat node, which we will
                        # represent as a separate binary_sensor
                        device = ISYBinarySensorHeartbeat(node, parent_device)
                        parent_device.add_heartbeat_device(device)
                        devices.append(device)
                elif device_class == 'motion' and device_type is not None and \
                        device_type.startswith('16.1.65.'):
                    # Special case for Insteon Motion Sensor (1st Gen):
                    if subnode_id == 2:
                        # Subnode 2 is the Dusk/Dawn sensor
                        device = ISYBinarySensorDevice(node, 'light')
                        devices.append(device)
                    elif subnode_id == 3:
                        # Subnode 3 is the low battery node
                        # Node never reports status until battery is low so
                        # the intial state is forced "OFF"/"NORMAL" if the
                        # parent device has a valid state.
                        inital_state = None if parent_device.is_unknown() \
                                             else False
                        device = ISYBinarySensorDevice(node, 'battery',
                                                       inital_state)
                        devices.append(device)
                else:
                    # We don't yet have any special logic for other sensor
                    # types, so add the nodes as individual devices
                    device = ISYBinarySensorDevice(node, device_class)
                    devices.append(device)
        else:  # Climate Devices
            if subnode_id == 2:
                # Subnode 2 is the "Cool Control" sensor
                # It never reports its state until first use is
                # detected after an ISY Restart, so we assume it's off.
                # As soon as the ISY Event Stream connects if it has a
                # valid state, it will be set.
                device = ISYBinarySensorDevice(node, 'cold', False)
                devices.append(device)
            elif subnode_id == 3:
                # Subnode 3 is the "Heat Control" sensor
                device = ISYBinarySensorDevice(node, 'heat', False)
                devices.append(device)

    for name, status, _ in hass.data[ISY994_PROGRAMS][DOMAIN]:
        devices.append(ISYBinarySensorProgram(name, status))

    for vcfg, vname, vobj in hass.data[ISY994_VARIABLES][DOMAIN]:
        devices.append(ISYBinarySensorVariableDevice(vcfg, vname, vobj))

    add_entities(devices)


def _detect_device_type(node) -> (str, str):
    try:
        device_type = node.type
    except AttributeError:
        # The type attribute didn't exist in the ISY's API response
        return (None, None)

    # Z-Wave Devices:
    if device_type[0] == '4':
        device_type = 'Z{}'.format(node.devtype_cat)
        for device_class in [*ZWAVE_BIN_SENS_DEVICE_TYPES]:
            if node.devtype_cat in ZWAVE_BIN_SENS_DEVICE_TYPES[device_class]:
                return device_class, device_type
    else:  # Other devices (incl Insteon.)
        for device_class in [*ISY_BIN_SENS_DEVICE_TYPES]:
            if any([device_type.startswith(t) for t in
                    set(ISY_BIN_SENS_DEVICE_TYPES[device_class])]):
                return device_class, device_type

    return (None, device_type)


def _is_val_unknown(val):
    """Determine if a number value represents UNKNOWN from PyISY."""
    return val == -1*float('inf')


class ISYBinarySensorDevice(ISYDevice, BinarySensorDevice):
    """Representation of an ISY994 binary sensor device.

    Often times, a single device is represented by multiple nodes in the ISY,
    allowing for different nuances in how those devices report their on and
    off events. This class turns those multiple nodes in to a single Hass
    entity and handles both ways that ISY binary sensors can work.
    """

    def __init__(self, node, force_device_class=None,
                 unknown_state=None) -> None:
        """Initialize the ISY994 binary sensor device."""
        super().__init__(node)
        self._negative_node = None
        self._heartbeat_device = None
        self._device_class_from_type = force_device_class
        # pylint: disable=protected-access
        if _is_val_unknown(self._node.status._val):
            self._computed_state = unknown_state
            self._status_was_unknown = True
        else:
            self._computed_state = bool(self._node.status._val)
            self._status_was_unknown = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node and subnode event emitters."""
        await super().async_added_to_hass()

        self._node.controlEvents.subscribe(self._positive_node_control_handler)

        if self._negative_node is not None:
            self._negative_node.controlEvents.subscribe(
                self._negative_node_control_handler)

    def add_heartbeat_device(self, device) -> None:
        """Register a heartbeat device for this sensor.

        The heartbeat node beats on its own, but we can gain a little
        reliability by considering any node activity for this sensor
        to be a heartbeat as well.
        """
        self._heartbeat_device = device

    def _heartbeat(self) -> None:
        """Send a heartbeat to our heartbeat device, if we have one."""
        if self._heartbeat_device is not None:
            self._heartbeat_device.heartbeat()

    def add_negative_node(self, child) -> None:
        """Add a negative node to this binary sensor device.

        The negative node is a node that can receive the 'off' events
        for the sensor, depending on device configuration and type.
        """
        self._negative_node = child

        # pylint: disable=protected-access
        if not _is_val_unknown(self._negative_node.status._val):
            # If the negative node has a value, it means the negative node is
            # in use for this device. Next we need to check to see if the
            # negative and positive nodes disagree on the state (both ON or
            # both OFF).
            if self._negative_node.status._val == self._node.status._val:
                # The states disagree, therefore we cannot determine the state
                # of the sensor until we receive our first ON event.
                self._computed_state = None

    def _negative_node_control_handler(self, event: object) -> None:
        """Handle an "On" control event from the "negative" node."""
        if event == 'DON':
            _LOGGER.debug("Sensor %s turning Off via the Negative node "
                          "sending a DON command", self.name)
            self._computed_state = False
            self.schedule_update_ha_state()
            self._heartbeat()

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
            self._heartbeat()
        if event == 'DOF':
            _LOGGER.debug("Sensor %s turning Off via the Primary node "
                          "sending a DOF command", self.name)
            self._computed_state = False
            self.schedule_update_ha_state()
            self._heartbeat()

    def on_update(self, event: object) -> None:
        """Primary node status updates.

        We MOSTLY ignore these updates, as we listen directly to the Control
        events on all nodes for this device. However, there is one edge case:
        If a leak sensor is unknown, due to a recent reboot of the ISY, the
        status will get updated to dry upon the first heartbeat. This status
        update is the only way that a leak sensor's status changes without
        an accompanying Control event, so we need to watch for it.
        """
        if self._status_was_unknown and self._computed_state is None:
            self._computed_state = bool(int(self._node.status))
            self._status_was_unknown = False
            self.schedule_update_ha_state()
            self._heartbeat()

    @property
    def value(self) -> object:
        """Get the current value of the device.

        Insteon leak sensors set their primary node to On when the state is
        DRY, not WET, so we invert the binary state if the user indicates
        that it is a moisture sensor.
        """
        if self._computed_state is None:
            # Do this first so we don't invert None on moisture sensors
            return None

        if self.device_class == 'moisture':
            return not self._computed_state

        return self._computed_state

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 binary sensor device is on.

        Note: This method will return false if the current state is UNKNOWN
        """
        return bool(self.value)

    @property
    def state(self):
        """Return the state of the binary sensor."""
        if self._computed_state is None:
            return None
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def device_class(self) -> str:
        """Return the class of this device.

        This was discovered by parsing the device type code during init
        """
        return self._device_class_from_type


class ISYBinarySensorHeartbeat(ISYDevice, BinarySensorDevice):
    """Representation of the battery state of an ISY994 sensor."""

    def __init__(self, node, parent_device) -> None:
        """Initialize the ISY994 binary sensor device.

        Computed state is set to UNKNOWN unless the ISY provided a valid
        state. See notes above regarding ISY Sensor status on ISY restart.
        If a valid state is provided (either on or off), the computed state in
        HA is set to OFF (Normal). If the heartbeat is not received in 25 hours
        then the computed state is set to ON (Low Battery).
        """
        super().__init__(node)
        self._parent_device = parent_device
        self._heartbeat_timer = None
        self._computed_state = None
        if not self.is_unknown():
            self._computed_state = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node and subnode event emitters."""
        await super().async_added_to_hass()

        self._node.controlEvents.subscribe(
            self._heartbeat_node_control_handler)

        # Start the timer on bootup, so we can change from UNKNOWN to OFF
        self._restart_timer()

    def _heartbeat_node_control_handler(self, event: object) -> None:
        """Update the heartbeat timestamp when any ON/OFF event is sent.

        The ISY uses both DON and DOF commands (alternating) for a heartbeat.
        """
        if event in ['DON', 'DOF']:
            self.heartbeat()

    def heartbeat(self):
        """Mark the device as online, and restart the 25 hour timer.

        This gets called when the heartbeat node beats, but also when the
        parent sensor sends any events, as we can trust that to mean the device
        is online. This mitigates the risk of false positives due to a single
        missed heartbeat event.
        """
        self._computed_state = False
        self._restart_timer()
        self.schedule_update_ha_state()

    def _restart_timer(self):
        """Restart the 25 hour timer."""
        try:
            self._heartbeat_timer()
            self._heartbeat_timer = None
        except TypeError:
            # No heartbeat timer is active
            pass

        @callback
        def timer_elapsed(now) -> None:
            """Heartbeat missed; set state to ON to indicate dead battery."""
            self._computed_state = True
            self._heartbeat_timer = None
            self.schedule_update_ha_state()

        point_in_time = dt_util.utcnow() + timedelta(hours=25)
        _LOGGER.debug("Heartbeat timer starting. Now: %s Then: %s",
                      dt_util.utcnow(), point_in_time)

        self._heartbeat_timer = async_track_point_in_utc_time(
            self.hass, timer_elapsed, point_in_time)

    def on_update(self, event: object) -> None:
        """Ignore node status updates.

        We listen directly to the Control events for this device.
        """
        pass

    @property
    def value(self) -> object:
        """Get the current value of this sensor."""
        return self._computed_state

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 binary sensor device is on.

        Note: This method will return false if the current state is UNKNOWN
        """
        return bool(self.value)

    @property
    def state(self):
        """Return the state of the binary sensor."""
        if self._computed_state is None:
            return None
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def device_class(self) -> str:
        """Get the class of this device."""
        return 'battery'

    @property
    def device_state_attributes(self):
        """Get the state attributes for the device."""
        attr = super().device_state_attributes
        attr['parent_entity_id'] = self._parent_device.entity_id
        return attr


class ISYBinarySensorProgram(ISYDevice, BinarySensorDevice):
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


class ISYBinarySensorVariableDevice(ISYDevice, BinarySensorDevice):
    """Representation of an ISY994 variable as a sensor device."""

    def __init__(self, vcfg: dict, vname: str, vobj: object) -> None:
        """Initialize the ISY994 binary sensor program."""
        super().__init__(vobj)
        self._config = vcfg
        self._name = vcfg.get(CONF_NAME, vname)
        self._vtype = vcfg.get(CONF_TYPE)
        self._vid = vcfg.get(CONF_ID)
        self._on_value = vcfg.get(CONF_PAYLOAD_ON)
        self._off_value = vcfg.get(CONF_PAYLOAD_OFF)
        self._change_handler = None
        self._init_change_handler = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.val.subscribe(
            'changed', self.on_update)
        self._init_change_handler = self._node.init.subscribe(
            'changed', self.on_update)

    @property
    def value(self) -> int:
        """Get the current value of the device."""
        return int(self._node.val)

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        attr = {}
        attr['init_value'] = int(self._node.init)
        return attr

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.value == self._on_value:
            return True
        if self.value == self._off_value:
            return False
        return None

    @property
    def icon(self):
        """Return the icon."""
        return self._config.get(CONF_ICON)

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._config.get(CONF_DEVICE_CLASS)
