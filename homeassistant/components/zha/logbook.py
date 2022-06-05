"""Describe ZHA logbook events."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.logbook.const import (
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import Event, HomeAssistant, callback
import homeassistant.helpers.device_registry as dr

from .core.const import DOMAIN as ZHA_DOMAIN, ZHA_EVENT
from .core.helpers import async_get_zha_device

if TYPE_CHECKING:
    from .core.device import ZHADevice


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""
    device_registry = dr.async_get(hass)

    @callback
    def async_describe_zha_event(event: Event) -> dict[str, str]:
        """Describe zha logbook event."""
        device: dr.DeviceEntry = device_registry.devices[event.data[ATTR_DEVICE_ID]]
        zha_device: ZHADevice = async_get_zha_device(hass, event.data[ATTR_DEVICE_ID])
        device_name: str = device.name_by_user or device.name or "Unknown device"
        event_data: dict = event.data
        event_type: str | None = None
        event_subtype: str | None = None

        if zha_device.device_automation_triggers:
            for (
                etype,
                subtype,
            ), trigger in zha_device.device_automation_triggers.items():
                event_data_schema = vol.Schema(
                    {vol.Required(key): value for key, value in trigger.items()},
                    extra=vol.ALLOW_EXTRA,
                )
                try:
                    if event_data_schema:
                        event_data_schema(event_data)
                    event_type = etype
                    event_subtype = subtype
                    break
                except vol.Invalid:
                    # If event doesn't match, skip event
                    continue

        if event_type is None:
            event_type = event_data["command"]

        if event_subtype is not None:
            event_type = f"{event_type.replace('_', ' ').title()} - {event_subtype.replace('_', ' ').title()}"

        message = f"{event_type} event was fired"
        if event_data["params"]:
            message = f"{message} with parameters: {event_data['params']}"

        return {
            LOGBOOK_ENTRY_NAME: device_name,
            LOGBOOK_ENTRY_MESSAGE: message,
        }

    async_describe_event(ZHA_DOMAIN, ZHA_EVENT, async_describe_zha_event)
