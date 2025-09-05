"""Describe Refoss logbook events."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    DOMAIN,
    EVENT_REFOSS_CLICK,
    INPUTS_EVENTS_TYPES,
)
from .coordinator import get_refoss_coordinator_by_device_id
from .utils import get_refoss_entity_name


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_refoss_click_event(event: Event) -> dict[str, str]:
        """Describe refoss.click logbook event."""
        device_id = event.data[ATTR_DEVICE_ID]
        click_type = event.data[ATTR_CLICK_TYPE]
        channel = event.data[ATTR_CHANNEL]
        input_name = f"{event.data[ATTR_DEVICE]} channel {channel}"

        if click_type in INPUTS_EVENTS_TYPES:
            coordinator = get_refoss_coordinator_by_device_id(hass, device_id)
            if coordinator and coordinator.device.initialized:
                key = f"input:{channel}"
                input_name = get_refoss_entity_name(coordinator.device, key)

        return {
            LOGBOOK_ENTRY_NAME: "Refoss",
            LOGBOOK_ENTRY_MESSAGE: (
                f"'{click_type}' click event for {input_name} Input was fired"
            ),
        }

    async_describe_event(DOMAIN, EVENT_REFOSS_CLICK, async_describe_refoss_click_event)
