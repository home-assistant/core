"""Representation of ISYEntity Types."""
from __future__ import annotations

from typing import Any

from pyisy.constants import (
    COMMAND_FRIENDLY_NAME,
    EMPTY_TIME,
    EVENT_PROPS_IGNORED,
    PROTO_GROUP,
    PROTO_INSTEON,
    PROTO_ZWAVE,
)
from pyisy.helpers import EventListener, NodeProperty
from pyisy.nodes import Node
from pyisy.programs import Program
from pyisy.variables import Variable

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, ISY_CONF_UUID, ISY_DEVICES


class ISYEntity(Entity):
    """Representation of an ISY device."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _node: Node | Program | Variable

    def __init__(self, node: Node) -> None:
        """Initialize the insteon device."""
        self._node = node
        self._attr_name = node.name
        uuid = node.isy.configuration[ISY_CONF_UUID]
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, uuid)})
        self._attr_unique_id = f"{uuid}_{node.address}"
        self._attrs: dict[str, Any] = {}
        self._change_handler: EventListener | None = None
        self._control_handler: EventListener | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.status_events.subscribe(self.async_on_update)

        if hasattr(self._node, "control_events"):
            self._control_handler = self._node.control_events.subscribe(
                self.async_on_control
            )

    @callback
    def async_on_update(self, event: NodeProperty) -> None:
        """Handle the update event from the ISY Node."""
        self.async_write_ha_state()

    @callback
    def async_on_control(self, event: NodeProperty) -> None:
        """Handle a control event from the ISY Node."""
        event_data = {
            "entity_id": self.entity_id,
            "control": event.control,
            "value": event.value,
            "formatted": event.formatted,
            "uom": event.uom,
            "precision": event.prec,
        }

        if event.control not in EVENT_PROPS_IGNORED:
            # New state attributes may be available, update the state.
            self.async_write_ha_state()

        self.hass.bus.async_fire("isy994_control", event_data)


class ISYNodeEntity(ISYEntity):
    """Representation of a ISY Nodebase (Node/Group) entity."""

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        assert self.platform and self.platform.config_entry

        entry_id = self.platform.config_entry.entry_id
        device_info: dict[str, DeviceInfo] = self.hass.data[DOMAIN][entry_id][
            ISY_DEVICES
        ]
        primary_address = self._node.primary_node

        if self._node.protocol == PROTO_GROUP:
            if len(self._node.controllers) == 1:
                # If Group has only 1 Controller, link to that device instead of the hub
                primary_address = self._node.isy.nodes.get_by_id(
                    self._node.controllers[0]
                ).primary_node
            else:
                return self._attr_device_info

        if device := device_info.get(primary_address):
            return device

        # Fall back to the hub if we don't have a primary device
        return self._attr_device_info

    @property
    def extra_state_attributes(self) -> dict:
        """Get the state attributes for the device.

        The 'aux_properties' in the pyisy Node class are combined with the
        other attributes which have been picked up from the event stream and
        the combined result are returned as the device state attributes.
        """
        attr = {}
        node = self._node
        # Insteon aux_properties are now their own sensors
        if (
            hasattr(self._node, "aux_properties")
            and getattr(node, "protocol", None) != PROTO_INSTEON
        ):
            for name, value in self._node.aux_properties.items():
                attr_name = COMMAND_FRIENDLY_NAME.get(name, name)
                attr[attr_name] = str(value.formatted).lower()

        # If a Group/Scene, set a property if the entire scene is on/off
        if hasattr(self._node, "group_all_on"):
            attr["group_all_on"] = STATE_ON if self._node.group_all_on else STATE_OFF

        self._attrs.update(attr)
        return self._attrs

    async def async_send_node_command(self, command: str) -> None:
        """Respond to an entity service command call."""
        if not hasattr(self._node, command):
            raise HomeAssistantError(
                f"Invalid service call: {command} for device {self.entity_id}"
            )
        await getattr(self._node, command)()

    async def async_send_raw_node_command(
        self,
        command: str,
        value: Any | None = None,
        unit_of_measurement: str | None = None,
        parameters: Any | None = None,
    ) -> None:
        """Respond to an entity service raw command call."""
        if not hasattr(self._node, "send_cmd"):
            raise HomeAssistantError(
                f"Invalid service call: {command} for device {self.entity_id}"
            )
        await self._node.send_cmd(command, value, unit_of_measurement, parameters)

    async def async_get_zwave_parameter(self, parameter: Any) -> None:
        """Respond to an entity service command to request a Z-Wave device parameter from the ISY."""
        if not hasattr(self._node, "protocol") or self._node.protocol != PROTO_ZWAVE:
            raise HomeAssistantError(
                "Invalid service call: cannot request Z-Wave Parameter for non-Z-Wave"
                f" device {self.entity_id}"
            )
        await self._node.get_zwave_parameter(parameter)

    async def async_set_zwave_parameter(
        self, parameter: Any, value: Any | None, size: int | None
    ) -> None:
        """Respond to an entity service command to set a Z-Wave device parameter via the ISY."""
        if not hasattr(self._node, "protocol") or self._node.protocol != PROTO_ZWAVE:
            raise HomeAssistantError(
                "Invalid service call: cannot set Z-Wave Parameter for non-Z-Wave"
                f" device {self.entity_id}"
            )
        await self._node.set_zwave_parameter(parameter, value, size)
        await self._node.get_zwave_parameter(parameter)

    async def async_rename_node(self, name: str) -> None:
        """Respond to an entity service command to rename a node on the ISY."""
        await self._node.rename(name)


class ISYProgramEntity(ISYEntity):
    """Representation of an ISY program base."""

    def __init__(self, name: str, status: Any | None, actions: Program = None) -> None:
        """Initialize the ISY program-based entity."""
        super().__init__(status)
        self._attr_name = name
        self._actions = actions

    @property
    def extra_state_attributes(self) -> dict:
        """Get the state attributes for the device."""
        attr = {}
        if self._actions:
            attr["actions_enabled"] = self._actions.enabled
            if self._actions.last_finished != EMPTY_TIME:
                attr["actions_last_finished"] = self._actions.last_finished
            if self._actions.last_run != EMPTY_TIME:
                attr["actions_last_run"] = self._actions.last_run
            if self._actions.last_update != EMPTY_TIME:
                attr["actions_last_update"] = self._actions.last_update
            attr["ran_else"] = self._actions.ran_else
            attr["ran_then"] = self._actions.ran_then
            attr["run_at_startup"] = self._actions.run_at_startup
            attr["running"] = self._actions.running
        attr["status_enabled"] = self._node.enabled
        if self._node.last_finished != EMPTY_TIME:
            attr["status_last_finished"] = self._node.last_finished
        if self._node.last_run != EMPTY_TIME:
            attr["status_last_run"] = self._node.last_run
        if self._node.last_update != EMPTY_TIME:
            attr["status_last_update"] = self._node.last_update
        return attr
