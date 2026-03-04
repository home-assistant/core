"""Event platform for Flic Button integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlicButtonConfigEntry
from .const import (
    CONF_PUSH_TWIST_MODE,
    EVENT_CLASS_BUTTON,
    EVENT_TYPE_CLICK,
    EVENT_TYPE_DOUBLE_CLICK,
    EVENT_TYPE_DOWN,
    EVENT_TYPE_HOLD,
    EVENT_TYPE_PUSH_TWIST_DECREMENT,
    EVENT_TYPE_PUSH_TWIST_INCREMENT,
    EVENT_TYPE_ROTATE_CLOCKWISE,
    EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE,
    EVENT_TYPE_SELECTOR_CHANGED,
    EVENT_TYPE_SWIPE_DOWN,
    EVENT_TYPE_SWIPE_LEFT,
    EVENT_TYPE_SWIPE_RIGHT,
    EVENT_TYPE_SWIPE_UP,
    EVENT_TYPE_TWIST_DECREMENT,
    EVENT_TYPE_TWIST_INCREMENT,
    EVENT_TYPE_UP,
    PushTwistMode,
)
from .coordinator import (
    FlicCoordinator,
    format_event_dispatcher_name,
    format_rotate_dispatcher_name,
)
from .entity import FlicButtonEntity

PARALLEL_UPDATES = 0

EVENT_DESCRIPTION = EventEntityDescription(
    key=EVENT_CLASS_BUTTON,
    translation_key=EVENT_CLASS_BUTTON,
    event_types=[
        EVENT_TYPE_UP,
        EVENT_TYPE_DOWN,
        EVENT_TYPE_CLICK,
        EVENT_TYPE_DOUBLE_CLICK,
        EVENT_TYPE_HOLD,
    ],
    device_class=EventDeviceClass.BUTTON,
)

# Duo button-specific descriptions with translation keys
# Duo buttons support all standard events plus swipe gestures and rotation
DUO_BUTTON_EVENT_TYPES: list[str] = [
    EVENT_TYPE_UP,
    EVENT_TYPE_DOWN,
    EVENT_TYPE_CLICK,
    EVENT_TYPE_DOUBLE_CLICK,
    EVENT_TYPE_HOLD,
    EVENT_TYPE_SWIPE_LEFT,
    EVENT_TYPE_SWIPE_RIGHT,
    EVENT_TYPE_SWIPE_UP,
    EVENT_TYPE_SWIPE_DOWN,
    EVENT_TYPE_ROTATE_CLOCKWISE,
    EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE,
]

DUO_SMALL_BUTTON_DESCRIPTION = EventEntityDescription(
    key=f"{EVENT_CLASS_BUTTON}_small",
    translation_key="button_small",
    event_types=DUO_BUTTON_EVENT_TYPES,
    device_class=EventDeviceClass.BUTTON,
)

DUO_BIG_BUTTON_DESCRIPTION = EventEntityDescription(
    key=f"{EVENT_CLASS_BUTTON}_big",
    translation_key="button_big",
    event_types=DUO_BUTTON_EVENT_TYPES,
    device_class=EventDeviceClass.BUTTON,
)

# Flic Twist description for SELECTOR mode - rotation and selector events
TWIST_SELECTOR_BUTTON_DESCRIPTION = EventEntityDescription(
    key=f"{EVENT_CLASS_BUTTON}_twist",
    translation_key="button_twist",
    event_types=[
        EVENT_TYPE_UP,
        EVENT_TYPE_DOWN,
        EVENT_TYPE_CLICK,
        EVENT_TYPE_DOUBLE_CLICK,
        EVENT_TYPE_HOLD,
        EVENT_TYPE_ROTATE_CLOCKWISE,
        EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE,
        EVENT_TYPE_SELECTOR_CHANGED,
    ],
    device_class=EventDeviceClass.BUTTON,
)

# Flic Twist description for DEFAULT mode - increment/decrement events
TWIST_DEFAULT_BUTTON_DESCRIPTION = EventEntityDescription(
    key=f"{EVENT_CLASS_BUTTON}_twist",
    translation_key="button_twist_default",
    event_types=[
        EVENT_TYPE_UP,
        EVENT_TYPE_DOWN,
        EVENT_TYPE_CLICK,
        EVENT_TYPE_DOUBLE_CLICK,
        EVENT_TYPE_HOLD,
        EVENT_TYPE_TWIST_INCREMENT,
        EVENT_TYPE_TWIST_DECREMENT,
        EVENT_TYPE_PUSH_TWIST_INCREMENT,
        EVENT_TYPE_PUSH_TWIST_DECREMENT,
    ],
    device_class=EventDeviceClass.BUTTON,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlicButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flic Button event entity."""
    coordinator = entry.runtime_data
    capabilities = coordinator.capabilities
    entities: list[FlicButtonEventEntity] = []

    push_twist_mode = PushTwistMode(
        entry.options.get(CONF_PUSH_TWIST_MODE, PushTwistMode.DEFAULT)
    )

    if capabilities.button_count == 1:
        # Single button device (Flic 2 or Twist)
        entities.append(
            FlicButtonEventEntity(
                coordinator,
                is_twist=capabilities.has_selector,  # Twist has selector
                push_twist_mode=push_twist_mode,
            )
        )
    else:
        # Multi-button device (Duo)
        entities.extend(
            FlicButtonEventEntity(coordinator, button_index=i)
            for i in range(capabilities.button_count)
        )

    async_add_entities(entities)


class FlicButtonEventEntity(FlicButtonEntity, EventEntity):
    """Representation of a Flic button event entity."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: FlicCoordinator,
        button_index: int | None = None,
        is_twist: bool = False,
        push_twist_mode: PushTwistMode = PushTwistMode.DEFAULT,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator)
        self._button_index = button_index
        self._is_twist = is_twist

        # Select entity description based on button type
        if is_twist and push_twist_mode == PushTwistMode.SELECTOR:
            # Flic Twist SELECTOR mode with rotation and selector events
            self.entity_description = TWIST_SELECTOR_BUTTON_DESCRIPTION
            self._attr_translation_key = "button_twist"
            unique_suffix = f"{EVENT_CLASS_BUTTON}_twist"
        elif is_twist:
            # Flic Twist DEFAULT/CONTINUOUS mode with increment/decrement events
            self.entity_description = TWIST_DEFAULT_BUTTON_DESCRIPTION
            self._attr_translation_key = "button_twist_default"
            unique_suffix = f"{EVENT_CLASS_BUTTON}_twist"
        elif button_index is None:
            # Flic 2 single button
            self.entity_description = EVENT_DESCRIPTION
            self._attr_translation_key = EVENT_CLASS_BUTTON
            unique_suffix = EVENT_CLASS_BUTTON
        elif button_index == 0:
            # Duo big button (button index 0)
            self.entity_description = DUO_BIG_BUTTON_DESCRIPTION
            self._attr_translation_key = "button_big"
            unique_suffix = f"{EVENT_CLASS_BUTTON}_big"
        else:
            # Duo small button (button index 1)
            self.entity_description = DUO_SMALL_BUTTON_DESCRIPTION
            self._attr_translation_key = "button_small"
            unique_suffix = f"{EVENT_CLASS_BUTTON}_small"

        self._attr_unique_id = f"{coordinator.client.address}-{unique_suffix}"

    async def async_added_to_hass(self) -> None:
        """Register event callbacks when entity is added."""
        await super().async_added_to_hass()

        # Subscribe to button events via dispatcher
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                format_event_dispatcher_name(self.coordinator.client.address),
                self._async_handle_event,
            )
        )

        # Subscribe to rotate events if device supports rotation
        if self.coordinator.capabilities.has_rotation:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    format_rotate_dispatcher_name(self.coordinator.client.address),
                    self._async_handle_rotate_event,
                )
            )

    @callback
    def _async_handle_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle button event from coordinator."""
        # For Duo buttons, filter events by button_index
        if self._button_index is not None:
            event_button_index = event_data.get("button_index")
            if event_button_index != self._button_index:
                # This event is for a different button
                return

        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()

    @callback
    def _async_handle_rotate_event(
        self, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """Handle rotate event from coordinator."""
        # Only trigger if the event type is in this entity's allowed event types
        if (
            self.entity_description.event_types is not None
            and event_type not in self.entity_description.event_types
        ):
            return

        # For Twist, accept all matching rotate events (no button_index filtering)
        if self._is_twist:
            self._trigger_event(event_type, event_data)
            self.async_write_ha_state()
            return

        # Filter rotate events by button_index (pressed button during rotation)
        if self._button_index is not None:
            event_button_index = event_data.get("button_index")
            if event_button_index != self._button_index:
                # This rotate event is for a different button
                return

        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()
