"""Describe Shelly logbook events."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import EventType

from . import get_block_device_wrapper, get_rpc_device_wrapper
from .const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    BLOCK_INPUTS_EVENTS_TYPES,
    DOMAIN,
    EVENT_SHELLY_CLICK,
    RPC_INPUTS_EVENTS_TYPES,
)
from .utils import get_block_device_name, get_rpc_entity_name


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[EventType], dict]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_shelly_click_event(event: EventType) -> dict[str, str]:
        """Describe shelly.click logbook event (block device)."""
        device_id = event.data[ATTR_DEVICE_ID]
        click_type = event.data[ATTR_CLICK_TYPE]
        channel = event.data[ATTR_CHANNEL]
        input_name = f"{event.data[ATTR_DEVICE]} channel {channel}"

        if click_type in RPC_INPUTS_EVENTS_TYPES:
            rpc_wrapper = get_rpc_device_wrapper(hass, device_id)
            if rpc_wrapper and rpc_wrapper.device.initialized:
                key = f"input:{channel-1}"
                input_name = get_rpc_entity_name(rpc_wrapper.device, key)

        elif click_type in BLOCK_INPUTS_EVENTS_TYPES:
            block_wrapper = get_block_device_wrapper(hass, device_id)
            if block_wrapper and block_wrapper.device.initialized:
                device_name = get_block_device_name(block_wrapper.device)
                input_name = f"{device_name} channel {channel}"

        return {
            LOGBOOK_ENTRY_NAME: "Shelly",
            LOGBOOK_ENTRY_MESSAGE: f"'{click_type}' click event for {input_name} Input was fired",
        }

    async_describe_event(DOMAIN, EVENT_SHELLY_CLICK, async_describe_shelly_click_event)
