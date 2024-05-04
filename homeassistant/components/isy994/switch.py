"""Support for ISY switches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyisy.constants import (
    ATTR_ACTION,
    ISY_VALUE_UNKNOWN,
    NC_NODE_ENABLED,
    PROTO_GROUP,
    TAG_ADDRESS,
)
from pyisy.helpers import EventListener
from pyisy.nodes import Node, NodeChangedEvent

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ISYAuxControlEntity, ISYNodeEntity, ISYProgramEntity
from .models import IsyData


@dataclass(frozen=True)
class ISYSwitchEntityDescription(SwitchEntityDescription):
    """Describes IST switch."""

    # ISYEnableSwitchEntity does not support UNDEFINED or None,
    # restrict the type to str.
    name: str = ""


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY switch platform."""
    isy_data: IsyData = hass.data[DOMAIN][entry.entry_id]
    entities: list[
        ISYSwitchProgramEntity | ISYSwitchEntity | ISYEnableSwitchEntity
    ] = []
    device_info = isy_data.devices
    for node in isy_data.nodes[Platform.SWITCH]:
        primary = node.primary_node
        if node.protocol == PROTO_GROUP and len(node.controllers) == 1:
            # If Group has only 1 Controller, link to that device instead of the hub
            primary = node.isy.nodes.get_by_id(node.controllers[0]).primary_node

        entities.append(ISYSwitchEntity(node, device_info.get(primary)))

    for name, status, actions in isy_data.programs[Platform.SWITCH]:
        entities.append(ISYSwitchProgramEntity(name, status, actions))

    for node, control in isy_data.aux_properties[Platform.SWITCH]:
        # Currently only used for enable switches, will need to be updated for
        # NS support by making sure control == TAG_ENABLED
        description = ISYSwitchEntityDescription(
            key=control,
            device_class=SwitchDeviceClass.SWITCH,
            name=control.title(),
            entity_category=EntityCategory.CONFIG,
        )
        entities.append(
            ISYEnableSwitchEntity(
                node=node,
                control=control,
                unique_id=f"{isy_data.uid_base(node)}_{control}",
                description=description,
                device_info=device_info.get(node.primary_node),
            )
        )
    async_add_entities(entities)


class ISYSwitchEntity(ISYNodeEntity, SwitchEntity):
    """Representation of an ISY switch device."""

    @property
    def is_on(self) -> bool | None:
        """Get whether the ISY device is in the on state."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return bool(self._node.status)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY switch."""
        if not await self._node.turn_off():
            raise HomeAssistantError(f"Unable to turn off switch {self._node.address}")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the turn on command to the ISY switch."""
        if not await self._node.turn_on():
            raise HomeAssistantError(f"Unable to turn on switch {self._node.address}")

    @property
    def icon(self) -> str | None:
        """Get the icon for groups."""
        if hasattr(self._node, "protocol") and self._node.protocol == PROTO_GROUP:
            return "mdi:google-circles-communities"  # Matches isy scene icon
        return super().icon


class ISYSwitchProgramEntity(ISYProgramEntity, SwitchEntity):
    """A representation of an ISY program switch."""

    _attr_icon = "mdi:script-text-outline"  # Matches isy program icon

    @property
    def is_on(self) -> bool:
        """Get whether the ISY switch program is on."""
        return bool(self._node.status)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the turn on command to the ISY switch program."""
        if not await self._actions.run_then():
            raise HomeAssistantError(
                f"Unable to run 'then' clause on program switch {self._actions.address}"
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY switch program."""
        if not await self._actions.run_else():
            raise HomeAssistantError(
                f"Unable to run 'else' clause on program switch {self._actions.address}"
            )


class ISYEnableSwitchEntity(ISYAuxControlEntity, SwitchEntity):
    """A representation of an ISY enable/disable switch."""

    def __init__(
        self,
        node: Node,
        control: str,
        unique_id: str,
        description: ISYSwitchEntityDescription,
        device_info: DeviceInfo | None,
    ) -> None:
        """Initialize the ISY Aux Control Number entity."""
        super().__init__(
            node=node,
            control=control,
            unique_id=unique_id,
            description=description,
            device_info=device_info,
        )
        self._attr_name = description.name  # Override super
        self._change_handler: EventListener = None

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Subscribe to the node control change events."""
        self._change_handler = self._node.isy.nodes.status_events.subscribe(
            self.async_on_update,
            event_filter={
                TAG_ADDRESS: self._node.address,
                ATTR_ACTION: NC_NODE_ENABLED,
            },
            key=self.unique_id,
        )

    @callback
    def async_on_update(self, event: NodeChangedEvent, key: str) -> None:
        """Handle a control event from the ISY Node."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True  # Enable switch is always available

    @property
    def is_on(self) -> bool | None:
        """Get whether the ISY device is in the on state."""
        return bool(self._node.enabled)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY switch."""
        if not await self._node.disable():
            raise HomeAssistantError(f"Unable to disable device {self._node.address}")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the turn on command to the ISY switch."""
        if not await self._node.enable():
            raise HomeAssistantError(f"Unable to enable device {self._node.address}")
