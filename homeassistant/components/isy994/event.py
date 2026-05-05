"""Event entities for ISY Insteon load and keypad-button nodes.

Each entity represents a physical button on the device and emits one of the
``event_types`` below when its corresponding control event arrives from the
ISY. KeypadLinc sub-button entities are disabled by default to avoid
registering large numbers of unused entities for users who don't need them.
"""

from __future__ import annotations

from typing import Final

from pyisy.constants import (
    ATTR_ACTION,
    CMD_FADE_DOWN,
    CMD_FADE_STOP,
    CMD_FADE_UP,
    CMD_OFF,
    CMD_OFF_FAST,
    CMD_ON,
    CMD_ON_FAST,
    NC_NODE_ENABLED,
    TAG_ADDRESS,
)
from pyisy.helpers import NodeProperty
from pyisy.nodes import Node, NodeChangedEvent

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EVENT_BUTTON_UNIQUE_ID_SUFFIX
from .entity import ISYNodeEntity
from .models import IsyConfigEntry

CONTROL_TO_EVENT_TYPE: Final[dict[str, str]] = {
    CMD_ON: "on",
    CMD_OFF: "off",
    CMD_ON_FAST: "fast_on",
    CMD_OFF_FAST: "fast_off",
    CMD_FADE_UP: "fade_up",
    CMD_FADE_DOWN: "fade_down",
    CMD_FADE_STOP: "fade_stop",
}

BUTTON_DESCRIPTION: Final[EventEntityDescription] = EventEntityDescription(
    key="button",
    translation_key="button",
    device_class=EventDeviceClass.BUTTON,
    event_types=list(CONTROL_TO_EVENT_TYPE.values()),
)


def _sub_button_name(node: Node) -> str:
    """Return the sub-button label with the parent device prefix stripped.

    ISY users commonly label KeypadLinc sub-buttons as ``"<device> <suffix>"``
    (e.g. ``"Hallway Keypad B"``). With ``has_entity_name=True``, Home
    Assistant prepends the device name to the entity name when rendering the
    friendly name, so we strip the prefix here to avoid duplication like
    ``"Hallway Keypad Hallway Keypad B"``. Falls back to the raw node name
    when the prefix doesn't match. The label is user-supplied in the ISY
    admin console and is not translatable.
    """
    parent_name: str = node.parent_node.name
    name: str = node.name
    if name.startswith(parent_name):
        return name[len(parent_name) :].lstrip(" -_:.") or name
    return name


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IsyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ISY event platform."""
    isy_data = entry.runtime_data
    device_info = isy_data.devices
    async_add_entities(
        ISYButtonEvent(node, device_info.get(node.primary_node))
        for node in isy_data.nodes[Platform.EVENT]
    )


class ISYButtonEvent(ISYNodeEntity, EventEntity):
    """Event entity that emits press/fast/fade events from an ISY node."""

    entity_description = BUTTON_DESCRIPTION
    _attr_has_entity_name = True

    def __init__(self, node: Node, device_info: DeviceInfo | None = None) -> None:
        """Initialize the ISY button event entity."""
        super().__init__(node, device_info=device_info)
        self._attr_unique_id = (
            f"{node.isy.uuid}_{node.address}{EVENT_BUTTON_UNIQUE_ID_SUFFIX}"
        )
        if node.parent_node is None:
            self._attr_name = None
        else:
            # Sub-button:
            self._attr_name = _sub_button_name(node)
            # Disabled by default — a typical KeypadLinc exposes 6-8 of
            # these and most users only automate a few.
            self._attr_entity_registry_enabled_default = False

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Subscribe to control events and node enabled/disabled changes only.

        Skipping the base class's status_events subscription avoids a state
        write on every value update; availability still tracks the node's
        enabled flag via a filtered subscription.
        """
        if hasattr(self._node, "control_events"):
            self._control_handler = self._node.control_events.subscribe(
                self.async_on_control
            )
        self._change_handler = self._node.isy.nodes.status_events.subscribe(
            self._async_on_availability_change,
            event_filter={
                TAG_ADDRESS: self._node.address,
                ATTR_ACTION: NC_NODE_ENABLED,
            },
            key=self.unique_id,
        )

    @callback
    def _async_on_availability_change(self, event: NodeChangedEvent, key: str) -> None:
        """Refresh state when the node is enabled or disabled."""
        self.async_write_ha_state()

    @callback
    def async_on_control(self, event: NodeProperty) -> None:
        """Trigger the entity, bypassing the base class's bus.fire.

        The load entity for the same node still fires `isy994_control` via
        the base class, so we don't fire it here to avoid double-emission.
        """
        event_type = CONTROL_TO_EVENT_TYPE.get(event.control)
        if event_type is None:
            return
        self._trigger_event(event_type)
        self.async_write_ha_state()
