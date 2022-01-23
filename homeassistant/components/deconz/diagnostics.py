"""Diagnostics support for deCONZ."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.system_info import async_get_system_info

from .gateway import get_gateway_from_config_entry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    diag: dict[str, Any] = {}

    diag["home_assistant"] = await async_get_system_info(hass)
    diag["config_entry"] = dict(config_entry.data)
    diag["deconz_config"] = gateway.api.config.raw
    diag["websocket_state"] = gateway.api.websocket.state
    diag["deconz_ids"] = gateway.deconz_ids
    diag["entities"] = gateway.entities
    diag["events"] = {
        event.serial: {
            "event_id": event.event_id,
            "event_type": type(event).__name__,
        }
        for event in gateway.events
    }
    diag["alarm_systems"] = {k: v.raw for k, v in gateway.api.alarmsystems.items()}
    diag["groups"] = {k: v.raw for k, v in gateway.api.groups.items()}
    diag["lights"] = {k: v.raw for k, v in gateway.api.lights.items()}
    diag["scenes"] = {k: v.raw for k, v in gateway.api.scenes.items()}
    diag["sensors"] = {k: v.raw for k, v in gateway.api.sensors.items()}

    return diag
