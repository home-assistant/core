"""Describe Shelly logbook events."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    BLOCK_INPUTS_EVENTS_TYPES,
    DOMAIN,
    EVENT_SHELLY_CLICK,
    RPC_INPUTS_EVENTS_TYPES,
)
from .coordinator import (
    get_block_coordinator_by_device_id,
    get_rpc_coordinator_by_device_id,
)
from .utils import get_rpc_entity_name


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_shelly_click_event(event: Event) -> dict[str, str]:
        """Describe shelly.click logbook event (block device)."""
        device_id = event.data[ATTR_DEVICE_ID]
        click_type = event.data[ATTR_CLICK_TYPE]
        channel = event.data[ATTR_CHANNEL]
        input_name = f"{event.data[ATTR_DEVICE]} channel {channel}"

        if click_type in RPC_INPUTS_EVENTS_TYPES:
            rpc_coordinator = get_rpc_coordinator_by_device_id(hass, device_id)
            if rpc_coordinator and rpc_coordinator.device.initialized:
                key = f"input:{channel-1}"
                input_name = get_rpc_entity_name(rpc_coordinator.device, key)

        elif click_type in BLOCK_INPUTS_EVENTS_TYPES:
            block_coordinator = get_block_coordinator_by_device_id(hass, device_id)
            if block_coordinator and block_coordinator.device.initialized:
                input_name = f"{block_coordinator.device.name} channel {channel}"

        return {
            LOGBOOK_ENTRY_NAME: "Shelly",
            LOGBOOK_ENTRY_MESSAGE: (
                f"'{click_type}' click event for {input_name} Input was fired"
            ),
        }

    async_describe_event(DOMAIN, EVENT_SHELLY_CLICK, async_describe_shelly_click_event)
