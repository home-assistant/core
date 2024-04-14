"""Support for ISY binary sensors."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pyisy.constants import (
    CMD_OFF,
    CMD_ON,
    ISY_VALUE_UNKNOWN,
    PROTO_INSTEON,
    PROTO_ZWAVE,
)
from pyisy.helpers import NodeProperty
from pyisy.nodes import Group, Node

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    _LOGGER,
    BINARY_SENSOR_DEVICE_TYPES_ISY,
    BINARY_SENSOR_DEVICE_TYPES_ZWAVE,
    DOMAIN,
    SUBNODE_CLIMATE_COOL,
    SUBNODE_CLIMATE_HEAT,
    SUBNODE_DUSK_DAWN,
    SUBNODE_HEARTBEAT,
    SUBNODE_LOW_BATTERY,
    SUBNODE_MOTION_DISABLED,
    SUBNODE_NEGATIVE,
    SUBNODE_TAMPER,
    TYPE_CATEGORY_CLIMATE,
    TYPE_INSTEON_MOTION,
)
from .entity import ISYNodeEntity, ISYProgramEntity
from .models import IsyData

DEVICE_PARENT_REQUIRED = [
    BinarySensorDeviceClass.OPENING,
    BinarySensorDeviceClass.MOISTURE,
    BinarySensorDeviceClass.MOTION,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY binary sensor platform."""
    entities: list[
        ISYInsteonBinarySensorEntity
        | ISYBinarySensorEntity
        | ISYBinarySensorHeartbeat
        | ISYBinarySensorProgramEntity
    ] = []
    entities_by_address: dict[
        str,
        ISYInsteonBinarySensorEntity
        | ISYBinarySensorEntity
        | ISYBinarySensorHeartbeat
        | ISYBinarySensorProgramEntity,
    ] = {}
    child_nodes: list[
        tuple[Node, BinarySensorDeviceClass | None, str | None, DeviceInfo | None]
    ] = []
    entity: (
        ISYInsteonBinarySensorEntity
        | ISYBinarySensorEntity
        | ISYBinarySensorHeartbeat
        | ISYBinarySensorProgramEntity
    )

    isy_data: IsyData = hass.data[DOMAIN][entry.entry_id]
    devices: dict[str, DeviceInfo] = isy_data.devices
    for node in isy_data.nodes[Platform.BINARY_SENSOR]:
        assert isinstance(node, Node)
        device_info = devices.get(node.primary_node)
        device_class, device_type = _detect_device_type_and_class(node)
        if node.protocol == PROTO_INSTEON:
            if node.parent_node is not None:
                # We'll process the Insteon child nodes last, to ensure all parent
                # nodes have been processed
                child_nodes.append((node, device_class, device_type, device_info))
                continue
            entity = ISYInsteonBinarySensorEntity(
                node, device_class, device_info=device_info
            )
        else:
            entity = ISYBinarySensorEntity(node, device_class, device_info=device_info)
        entities.append(entity)
        entities_by_address[node.address] = entity

    # Handle some special child node cases for Insteon Devices
    for node, device_class, device_type, device_info in child_nodes:
        subnode_id = int(node.address.split(" ")[-1], 16)
        # Handle Insteon Thermostats
        if device_type is not None and device_type.startswith(TYPE_CATEGORY_CLIMATE):
            if subnode_id == SUBNODE_CLIMATE_COOL:
                # Subnode 2 is the "Cool Control" sensor
                # It never reports its state until first use is
                # detected after an ISY Restart, so we assume it's off.
                # As soon as the ISY Event Stream connects if it has a
                # valid state, it will be set.
                entity = ISYInsteonBinarySensorEntity(
                    node, BinarySensorDeviceClass.COLD, False, device_info=device_info
                )
                entities.append(entity)
            elif subnode_id == SUBNODE_CLIMATE_HEAT:
                # Subnode 3 is the "Heat Control" sensor
                entity = ISYInsteonBinarySensorEntity(
                    node, BinarySensorDeviceClass.HEAT, False, device_info=device_info
                )
                entities.append(entity)
            continue

        if device_class in DEVICE_PARENT_REQUIRED:
            parent_entity = entities_by_address.get(node.parent_node.address)
            if not parent_entity:
                _LOGGER.error(
                    (
                        "Node %s has a parent node %s, but no device "
                        "was created for the parent. Skipping"
                    ),
                    node.address,
                    node.parent_node,
                )
                continue

        if device_class in (
            BinarySensorDeviceClass.OPENING,
            BinarySensorDeviceClass.MOISTURE,
        ):
            # These sensors use an optional "negative" subnode 2 to
            # snag all state changes
            if subnode_id == SUBNODE_NEGATIVE:
                assert isinstance(parent_entity, ISYInsteonBinarySensorEntity)
                parent_entity.add_negative_node(node)
            elif subnode_id == SUBNODE_HEARTBEAT:
                assert isinstance(parent_entity, ISYInsteonBinarySensorEntity)
                # Subnode 4 is the heartbeat node, which we will
                # represent as a separate binary_sensor
                entity = ISYBinarySensorHeartbeat(
                    node, parent_entity, device_info=device_info
                )
                parent_entity.add_heartbeat_device(entity)
                entities.append(entity)
            continue
        if (
            device_class == BinarySensorDeviceClass.MOTION
            and device_type is not None
            and any(device_type.startswith(t) for t in TYPE_INSTEON_MOTION)
        ):
            # Special cases for Insteon Motion Sensors I & II:
            # Some subnodes never report status until activated, so
            # the initial state is forced "OFF"/"NORMAL" if the
            # parent device has a valid state. This is corrected
            # upon connection to the ISY event stream if subnode has a valid state.
            assert isinstance(parent_entity, ISYInsteonBinarySensorEntity)
            initial_state = None if parent_entity.state is None else False
            if subnode_id == SUBNODE_DUSK_DAWN:
                # Subnode 2 is the Dusk/Dawn sensor
                entity = ISYInsteonBinarySensorEntity(
                    node, BinarySensorDeviceClass.LIGHT, device_info=device_info
                )
                entities.append(entity)
                continue
            if subnode_id == SUBNODE_LOW_BATTERY:
                # Subnode 3 is the low battery node
                entity = ISYInsteonBinarySensorEntity(
                    node,
                    BinarySensorDeviceClass.BATTERY,
                    initial_state,
                    device_info=device_info,
                )
                entities.append(entity)
                continue
            if subnode_id in SUBNODE_TAMPER:
                # Tamper Sub-node for MS II. Sometimes reported as "A" sometimes
                # reported as "10", which translate from Hex to 10 and 16 resp.
                entity = ISYInsteonBinarySensorEntity(
                    node,
                    BinarySensorDeviceClass.PROBLEM,
                    initial_state,
                    device_info=device_info,
                )
                entities.append(entity)
                continue
            if subnode_id in SUBNODE_MOTION_DISABLED:
                # Motion Disabled Sub-node for MS II ("D" or "13")
                entity = ISYInsteonBinarySensorEntity(node, device_info=device_info)
                entities.append(entity)
                continue

        # We don't yet have any special logic for other sensor
        # types, so add the nodes as individual devices
        entity = ISYBinarySensorEntity(
            node, force_device_class=device_class, device_info=device_info
        )
        entities.append(entity)

    for name, status, _ in isy_data.programs[Platform.BINARY_SENSOR]:
        entities.append(ISYBinarySensorProgramEntity(name, status))

    async_add_entities(entities)


def _detect_device_type_and_class(
    node: Group | Node,
) -> tuple[BinarySensorDeviceClass | None, str | None]:
    try:
        device_type = node.type
    except AttributeError:
        # The type attribute didn't exist in the ISY's API response
        return (None, None)

    # Z-Wave Devices:
    if node.protocol == PROTO_ZWAVE:
        device_type = f"Z{node.zwave_props.category}"
        for device_class, values in BINARY_SENSOR_DEVICE_TYPES_ZWAVE.items():
            if node.zwave_props.category in values:
                return device_class, device_type
        return (None, device_type)

    # Other devices (incl Insteon.)
    for device_class, values in BINARY_SENSOR_DEVICE_TYPES_ISY.items():
        if any(device_type.startswith(t) for t in values):
            return device_class, device_type
    return (None, device_type)


class ISYBinarySensorEntity(ISYNodeEntity, BinarySensorEntity):
    """Representation of a basic ISY binary sensor device."""

    def __init__(
        self,
        node: Node,
        force_device_class: BinarySensorDeviceClass | None = None,
        unknown_state: bool | None = None,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize the ISY binary sensor device."""
        super().__init__(node, device_info=device_info)
        # This was discovered by parsing the device type code during init
        self._attr_device_class = force_device_class

    @property
    def is_on(self) -> bool | None:
        """Get whether the ISY binary sensor device is on."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return bool(self._node.status)


class ISYInsteonBinarySensorEntity(ISYBinarySensorEntity):
    """Representation of an ISY Insteon binary sensor device.

    Often times, a single device is represented by multiple nodes in the ISY,
    allowing for different nuances in how those devices report their on and
    off events. This class turns those multiple nodes into a single Home
    Assistant entity and handles both ways that ISY binary sensors can work.
    """

    def __init__(
        self,
        node: Node,
        force_device_class: BinarySensorDeviceClass | None = None,
        unknown_state: bool | None = None,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize the ISY binary sensor device."""
        super().__init__(node, force_device_class, device_info=device_info)
        self._negative_node: Node | None = None
        self._heartbeat_device: ISYBinarySensorHeartbeat | None = None
        if self._node.status == ISY_VALUE_UNKNOWN:
            self._computed_state = unknown_state
            self._status_was_unknown = True
        else:
            self._computed_state = bool(self._node.status)
            self._status_was_unknown = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node and subnode event emitters."""
        await super().async_added_to_hass()

        self._node.control_events.subscribe(self._async_positive_node_control_handler)

        if self._negative_node is not None:
            self._negative_node.control_events.subscribe(
                self._async_negative_node_control_handler
            )

    def add_heartbeat_device(self, entity: ISYBinarySensorHeartbeat | None) -> None:
        """Register a heartbeat device for this sensor.

        The heartbeat node beats on its own, but we can gain a little
        reliability by considering any node activity for this sensor
        to be a heartbeat as well.
        """
        self._heartbeat_device = entity

    def _async_heartbeat(self) -> None:
        """Send a heartbeat to our heartbeat device, if we have one."""
        if self._heartbeat_device is not None:
            self._heartbeat_device.async_heartbeat()

    def add_negative_node(self, child: Node) -> None:
        """Add a negative node to this binary sensor device.

        The negative node is a node that can receive the 'off' events
        for the sensor, depending on device configuration and type.
        """
        self._negative_node = child

        # If the negative node has a value, it means the negative node is
        # in use for this device. Next we need to check to see if the
        # negative and positive nodes disagree on the state (both ON or
        # both OFF).
        if (
            self._negative_node.status != ISY_VALUE_UNKNOWN
            and self._negative_node.status == self._node.status
        ):
            # The states disagree, therefore we cannot determine the state
            # of the sensor until we receive our first ON event.
            self._computed_state = None

    @callback
    def _async_negative_node_control_handler(self, event: NodeProperty) -> None:
        """Handle an "On" control event from the "negative" node."""
        if event.control == CMD_ON:
            _LOGGER.debug(
                "Sensor %s turning Off via the Negative node sending a DON command",
                self.name,
            )
            self._computed_state = False
            self.async_write_ha_state()
            self._async_heartbeat()

    @callback
    def _async_positive_node_control_handler(self, event: NodeProperty) -> None:
        """Handle On and Off control event coming from the primary node.

        Depending on device configuration, sometimes only On events
        will come to this node, with the negative node representing Off
        events
        """
        if event.control == CMD_ON:
            _LOGGER.debug(
                "Sensor %s turning On via the Primary node sending a DON command",
                self.name,
            )
            self._computed_state = True
            self.async_write_ha_state()
            self._async_heartbeat()
        if event.control == CMD_OFF:
            _LOGGER.debug(
                "Sensor %s turning Off via the Primary node sending a DOF command",
                self.name,
            )
            self._computed_state = False
            self.async_write_ha_state()
            self._async_heartbeat()

    @callback
    def async_on_update(self, event: NodeProperty) -> None:
        """Primary node status updates.

        We MOSTLY ignore these updates, as we listen directly to the Control
        events on all nodes for this device. However, there is one edge case:
        If a leak sensor is unknown, due to a recent reboot of the ISY, the
        status will get updated to dry upon the first heartbeat. This status
        update is the only way that a leak sensor's status changes without
        an accompanying Control event, so we need to watch for it.
        """
        if self._status_was_unknown and self._computed_state is None:
            self._computed_state = bool(self._node.status)
            self._status_was_unknown = False
            self.async_write_ha_state()
            self._async_heartbeat()

    @property
    def is_on(self) -> bool | None:
        """Get whether the ISY binary sensor device is on.

        Insteon leak sensors set their primary node to On when the state is
        DRY, not WET, so we invert the binary state if the user indicates
        that it is a moisture sensor.

        Dusk/Dawn sensors set their node to On when DUSK, not light detected,
        so this is inverted as well.
        """
        if self._computed_state is None:
            # Do this first so we don't invert None on moisture or light sensors
            return None

        if self.device_class in (
            BinarySensorDeviceClass.LIGHT,
            BinarySensorDeviceClass.MOISTURE,
        ):
            return not self._computed_state

        return self._computed_state


class ISYBinarySensorHeartbeat(ISYNodeEntity, BinarySensorEntity, RestoreEntity):
    """Representation of the battery state of an ISY sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(
        self,
        node: Node,
        parent_device: ISYInsteonBinarySensorEntity
        | ISYBinarySensorEntity
        | ISYBinarySensorHeartbeat
        | ISYBinarySensorProgramEntity,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize the ISY binary sensor device.

        Computed state is set to UNKNOWN unless the ISY provided a valid
        state. See notes above regarding ISY Sensor status on ISY restart.
        If a valid state is provided (either on or off), the computed state in
        HA is restored to the previous value or defaulted to OFF (Normal).
        If the heartbeat is not received in 25 hours then the computed state is
        set to ON (Low Battery).
        """
        super().__init__(node, device_info=device_info)
        self._parent_device = parent_device
        self._heartbeat_timer: CALLBACK_TYPE | None = None
        self._computed_state: bool | None = None
        if self.state is None:
            self._computed_state = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node and subnode event emitters."""
        await super().async_added_to_hass()

        self._node.control_events.subscribe(self._heartbeat_node_control_handler)

        # Start the timer on bootup, so we can change from UNKNOWN to OFF
        self._restart_timer()

        if (last_state := await self.async_get_last_state()) is not None:
            # Only restore the state if it was previously ON (Low Battery)
            if last_state.state == STATE_ON:
                self._computed_state = True

    def _heartbeat_node_control_handler(self, event: NodeProperty) -> None:
        """Update the heartbeat timestamp when any ON/OFF event is sent.

        The ISY uses both DON and DOF commands (alternating) for a heartbeat.
        """
        if event.control in (CMD_ON, CMD_OFF):
            self.async_heartbeat()

    @callback
    def async_heartbeat(self) -> None:
        """Mark the device as online, and restart the 25 hour timer.

        This gets called when the heartbeat node beats, but also when the
        parent sensor sends any events, as we can trust that to mean the device
        is online. This mitigates the risk of false positives due to a single
        missed heartbeat event.
        """
        self._computed_state = False
        self._restart_timer()
        self.async_write_ha_state()

    def _restart_timer(self) -> None:
        """Restart the 25 hour timer."""
        if self._heartbeat_timer is not None:
            self._heartbeat_timer()
            self._heartbeat_timer = None

        @callback
        def timer_elapsed(now: datetime) -> None:
            """Heartbeat missed; set state to ON to indicate dead battery."""
            self._computed_state = True
            self._heartbeat_timer = None
            self.async_write_ha_state()

        self._heartbeat_timer = async_call_later(
            self.hass, timedelta(hours=25), timer_elapsed
        )

    @callback
    def async_on_update(self, event: object) -> None:
        """Ignore node status updates.

        We listen directly to the Control events for this device.
        """

    @property
    def is_on(self) -> bool:
        """Get whether the ISY binary sensor device is on.

        Note: This method will return false if the current state is UNKNOWN
        which occurs after a restart until the first heartbeat or control
        parent control event is received.
        """
        return bool(self._computed_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Get the state attributes for the device."""
        attr = super().extra_state_attributes
        attr["parent_entity_id"] = self._parent_device.entity_id
        return attr


class ISYBinarySensorProgramEntity(ISYProgramEntity, BinarySensorEntity):
    """Representation of an ISY binary sensor program.

    This does not need all of the subnode logic in the device version of binary
    sensors.
    """

    @property
    def is_on(self) -> bool:
        """Get whether the ISY binary sensor device is on."""
        return bool(self._node.status)
