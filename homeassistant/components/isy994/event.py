"""Event entities for ISY Insteon load and keypad-button nodes.

Each entity represents a physical button on the device and emits one of the
standard button event types (architecture#1377) when its corresponding
control event arrives from the ISY.
"""

from typing import TYPE_CHECKING, Final, NamedTuple, override

from pyisy.constants import (
    ATTR_ACTION,
    CMD_FADE_DOWN,
    CMD_FADE_STOP,
    CMD_FADE_UP,
    CMD_OFF,
    CMD_OFF_FAST,
    CMD_ON,
    CMD_ON_FAST,
    ES_CONNECTED,
    NC_NODE_ENABLED,
    TAG_ADDRESS,
)
from pyisy.helpers import NodeProperty
from pyisy.nodes import Node, NodeChangedEvent

from homeassistant.components.event import (
    ATTR_MULTI_PRESS_COUNT,
    ButtonEventType,
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ISYNodeEntity

if TYPE_CHECKING:
    from .models import IsyConfigEntry

EVENT_BUTTON_UNIQUE_ID_SUFFIX = "_button"

ATTR_DIRECTION = "direction"

DIRECTION_UP = "up"
DIRECTION_DOWN = "down"


class _ControlEvent(NamedTuple):
    """Standard event type + direction/count for one ISY control command."""

    event_type: ButtonEventType
    direction: str
    multi_press_count: int | None = None


# Maps to the architecture#1377 standard button event types. `direction`
# distinguishes the two paddle positions of a single physical button rather
# than splitting into two entities. CMD_FADE_STOP
# (long-press end) isn't listed here: its direction is whichever fade most
# recently started, tracked in `ISYButtonEvent._last_fade_direction`.
CONTROL_TO_EVENT: Final[dict[str, _ControlEvent]] = {
    CMD_ON: _ControlEvent(ButtonEventType.PRESS_END, DIRECTION_UP),
    CMD_OFF: _ControlEvent(ButtonEventType.PRESS_END, DIRECTION_DOWN),
    CMD_ON_FAST: _ControlEvent(ButtonEventType.MULTI_PRESS_END, DIRECTION_UP, 2),
    CMD_OFF_FAST: _ControlEvent(ButtonEventType.MULTI_PRESS_END, DIRECTION_DOWN, 2),
    CMD_FADE_UP: _ControlEvent(ButtonEventType.LONG_PRESS_START, DIRECTION_UP),
    CMD_FADE_DOWN: _ControlEvent(ButtonEventType.LONG_PRESS_START, DIRECTION_DOWN),
}

BUTTON_DESCRIPTION: Final[EventEntityDescription] = EventEntityDescription(
    key="button",
    translation_key="button",
    device_class=EventDeviceClass.BUTTON,
    event_types=[
        ButtonEventType.PRESS_END,
        ButtonEventType.MULTI_PRESS_END,
        ButtonEventType.LONG_PRESS_START,
        ButtonEventType.LONG_PRESS_END,
    ],
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
    if name.startswith(parent_name) and (
        len(name) == len(parent_name) or name[len(parent_name)] in " -_:."
    ):
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
        self._last_fade_direction: str | None = None
        if node.parent_node is None:
            self._attr_name = None
        else:
            # Sub-button:
            self._attr_name = _sub_button_name(node)
            # Disabled by default — a typical KeypadLinc exposes 6-8 of
            # these and most users only automate a few.
            self._attr_entity_registry_enabled_default = False

    @override
    # pylint: disable-next=home-assistant-missing-super-call
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
            self.async_on_remove(self._control_handler.unsubscribe)
        self._change_handler = self._node.isy.nodes.status_events.subscribe(
            self._async_on_availability_change,
            event_filter={
                TAG_ADDRESS: self._node.address,
                ATTR_ACTION: NC_NODE_ENABLED,
            },
            key=self.unique_id,
        )
        self.async_on_remove(self._change_handler.unsubscribe)

    @callback
    def _async_on_availability_change(self, event: NodeChangedEvent, key: str) -> None:
        """Refresh state when the node is enabled or disabled."""
        self.async_write_ha_state()

    @callback
    @override
    def async_on_control(self, event: NodeProperty) -> None:
        """Trigger the entity, bypassing the base class's bus.fire.

        The load entity for the same node still fires `isy994_control` via
        the base class, so we don't fire it here to avoid double-emission.
        Suppressed while the websocket isn't fully connected -- PyISY
        replays the current status of every node on (re)connect before
        settling, and without this guard that replay fires stale button
        events on every startup, config-entry reload, and reconnect.
        """
        websocket = self._node.isy.websocket
        if websocket is not None and websocket.status != ES_CONNECTED:
            return
        if event.control == CMD_FADE_STOP:
            self._trigger_event(
                ButtonEventType.LONG_PRESS_END,
                {ATTR_DIRECTION: self._last_fade_direction},
            )
            self.async_write_ha_state()
            return
        control_event = CONTROL_TO_EVENT.get(event.control)
        if control_event is None:
            return
        if control_event.event_type == ButtonEventType.LONG_PRESS_START:
            self._last_fade_direction = control_event.direction
        event_attributes: dict[str, str | int] = {
            ATTR_DIRECTION: control_event.direction
        }
        if control_event.multi_press_count is not None:
            event_attributes[ATTR_MULTI_PRESS_COUNT] = control_event.multi_press_count
        self._trigger_event(control_event.event_type, event_attributes)
        self.async_write_ha_state()
