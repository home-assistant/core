"""Describe Shelly logbook events."""
from __future__ import annotations

from typing import Callable

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import EventType

from . import get_device_wrapper
from .const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    DOMAIN,
    EVENT_SHELLY_CLICK,
)
from .utils import get_device_name


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[EventType], dict]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_shelly_click_event(event: EventType) -> dict[str, str]:
        """Describe shelly.click logbook event."""
        wrapper = get_device_wrapper(hass, event.data[ATTR_DEVICE_ID])
        if wrapper and wrapper.device.initialized:
            device_name = get_device_name(wrapper.device)
        else:
            device_name = event.data[ATTR_DEVICE]

        channel = event.data[ATTR_CHANNEL]
        click_type = event.data[ATTR_CLICK_TYPE]

        return {
            "name": "Shelly",
            "message": f"'{click_type}' click event for {device_name} channel {channel} was fired.",
        }

    async_describe_event(DOMAIN, EVENT_SHELLY_CLICK, async_describe_shelly_click_event)
