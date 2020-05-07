"""Support for ISY994 binary sensors."""
from datetime import timedelta
from typing import Callable

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR,
    BinarySensorEntity,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import ISY994_NODES, ISY994_PROGRAMS
from .const import _LOGGER, ISY_BIN_SENS_DEVICE_TYPES
from .entity import ISYNodeEntity, ISYProgramEntity


def setup_platform(
    hass, config: ConfigType, add_entities: Callable[[list], None], discovery_info=None
):
    """Set up the ISY994 binary sensor platform."""
    devices = []
    devices_by_address = {}
    child_nodes = []

    for node in hass.data[ISY994_NODES][BINARY_SENSOR]:
        if node.parent_node is None:
            device = ISYBinarySensorEntity(node)
            devices.append(device)
            devices_by_address[node.address] = device
        else:
            # We'll process the child nodes last, to ensure all parent nodes
            # have been processed
            child_nodes.append(node)

    for node in child_nodes:
        try:
            parent_device = devices_by_address[node.parent_node.address]
        except KeyError:
            _LOGGER.error(
                "Node %s has a parent node %s, but no device "
                "was created for the parent. Skipping.",
                node.address,
                node.primary_node,
            )
        else:
            device_type = _detect_device_type(node)
            subnode_id = int(node.address[-1], 16)
            if device_type in ("opening", "moisture"):
                # These sensors use an optional "negative" subnode 2 to snag
                # all state changes
                if subnode_id == 2:
                    parent_device.add_negative_node(node)
                elif subnode_id == 4:
                    # Subnode 4 is the heartbeat node, which we will represent
                    # as a separate binary_sensor
                    device = ISYBinarySensorHeartbeat(node, parent_device)
                    parent_device.add_heartbeat_device(device)
                    devices.append(device)
            else:
                # We don't yet have any special logic for other sensor types,
                # so add the nodes as individual devices
                device = ISYBinarySensorEntity(node)
                devices.append(device)

    for name, status, _ in hass.data[ISY994_PROGRAMS][BINARY_SENSOR]:
        devices.append(ISYBinarySensorProgramEntity(name, status))

    add_entities(devices)


def _detect_device_type(node) -> str:
    try:
        device_type = node.type
    except AttributeError:
        # The type attribute didn't exist in the ISY's API response
        return None

    split_type = device_type.split(".")
    for device_class, ids in ISY_BIN_SENS_DEVICE_TYPES.items():
        if f"{split_type[0]}.{split_type[1]}" in ids:
            return device_class

    return None


class ISYBinarySensorEntity(ISYNodeEntity, BinarySensorEntity):
    """Representation of an ISY994 binary sensor device.

    Often times, a single device is represented by multiple nodes in the ISY,
    allowing for different nuances in how those devices report their on and
    off events. This class turns those multiple nodes in to a single Home
    Assistant entity and handles both ways that ISY binary sensors can work.
    """

    def __init__(self, node) -> None:
        """Initialize the ISY994 binary sensor device."""
        super().__init__(node)
        self._negative_node = None
        self._heartbeat_device = None
        self._device_class_from_type = _detect_device_type(self._node)
        if self._node.status == ISY_VALUE_UNKNOWN:
            self._computed_state = None
            self._status_was_unknown = True
        else:
            self._computed_state = bool(self._node.status)
            self._status_was_unknown = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node and subnode event emitters."""
        await super().async_added_to_hass()

        self._node.control_events.subscribe(self._positive_node_control_handler)

        if self._negative_node is not None:
            self._negative_node.control_events.subscribe(
                self._negative_node_control_handler
            )

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

        if self._negative_node.status != ISY_VALUE_UNKNOWN:
            # If the negative node has a value, it means the negative node is
            # in use for this device. Next we need to check to see if the
            # negative and positive nodes disagree on the state (both ON or
            # both OFF).
            if self._negative_node.status == self._node.status:
                # The states disagree, therefore we cannot determine the state
                # of the sensor until we receive our first ON event.
                self._computed_state = None

    def _negative_node_control_handler(self, event: object) -> None:
        """Handle an "On" control event from the "negative" node."""
        if event.control == "DON":
            _LOGGER.debug(
                "Sensor %s turning Off via the Negative node sending a DON command",
                self.name,
            )
            self._computed_state = False
            self.schedule_update_ha_state()
            self._heartbeat()

    def _positive_node_control_handler(self, event: object) -> None:
        """Handle On and Off control event coming from the primary node.

        Depending on device configuration, sometimes only On events
        will come to this node, with the negative node representing Off
        events
        """
        if event.control == "DON":
            _LOGGER.debug(
                "Sensor %s turning On via the Primary node sending a DON command",
                self.name,
            )
            self._computed_state = True
            self.schedule_update_ha_state()
            self._heartbeat()
        if event.control == "DOF":
            _LOGGER.debug(
                "Sensor %s turning Off via the Primary node sending a DOF command",
                self.name,
            )
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

        if self.device_class == "moisture":
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


class ISYBinarySensorHeartbeat(ISYNodeEntity, BinarySensorEntity):
    """Representation of the battery state of an ISY994 sensor."""

    def __init__(self, node, parent_device) -> None:
        """Initialize the ISY994 binary sensor device."""
        super().__init__(node)
        self._computed_state = None
        self._parent_device = parent_device
        self._heartbeat_timer = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node and subnode event emitters."""
        await super().async_added_to_hass()

        self._node.control_events.subscribe(self._heartbeat_node_control_handler)

        # Start the timer on bootup, so we can change from UNKNOWN to ON
        self._restart_timer()

    def _heartbeat_node_control_handler(self, event: object) -> None:
        """Update the heartbeat timestamp when an On event is sent."""
        if event.control == "DON":
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
            """Heartbeat missed; set state to indicate dead battery."""
            self._computed_state = True
            self._heartbeat_timer = None
            self.schedule_update_ha_state()

        point_in_time = dt_util.utcnow() + timedelta(hours=25)
        _LOGGER.debug(
            "Timer starting. Now: %s Then: %s", dt_util.utcnow(), point_in_time
        )

        self._heartbeat_timer = async_track_point_in_utc_time(
            self.hass, timer_elapsed, point_in_time
        )

    def on_update(self, event: object) -> None:
        """Ignore node status updates.

        We listen directly to the Control events for this device.
        """

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
        return "battery"

    @property
    def device_state_attributes(self):
        """Get the state attributes for the device."""
        attr = super().device_state_attributes
        attr["parent_entity_id"] = self._parent_device.entity_id
        return attr


class ISYBinarySensorProgramEntity(ISYProgramEntity, BinarySensorEntity):
    """Representation of an ISY994 binary sensor program.

    This does not need all of the subnode logic in the device version of binary
    sensors.
    """

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 binary sensor device is on."""
        return bool(self.value)
