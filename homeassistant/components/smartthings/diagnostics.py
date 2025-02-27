"""Diagnostics support for SmartThings."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from pysmartthings import DeviceEvent

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import SmartThingsConfigEntry
from .const import DOMAIN

EVENT_WAIT_TIME = 5


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: SmartThingsConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    client = entry.runtime_data.client
    device_id = next(
        identifier for identifier in device.identifiers if identifier[0] == DOMAIN
    )[1]

    device_status = await client.get_device_status(device_id)

    events: list[DeviceEvent] = []

    def register_event(event: DeviceEvent) -> None:
        events.append(event)

    listener = client.add_device_event_listener(device_id, register_event)

    await asyncio.sleep(EVENT_WAIT_TIME)

    listener()

    status: dict[str, Any] = {}
    for component, capabilities in device_status.items():
        status[component] = {}
        for capability, attributes in capabilities.items():
            status[component][capability] = {}
            for attribute, value in attributes.items():
                status[component][capability][attribute] = asdict(value)
    return {"events": [asdict(event) for event in events], "status": status}
