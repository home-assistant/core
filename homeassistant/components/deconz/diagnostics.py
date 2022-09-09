"""Diagnostics support for deCONZ."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .gateway import get_gateway_from_config_entry

REDACT_CONFIG = {CONF_API_KEY, CONF_UNIQUE_ID}
REDACT_DECONZ_CONFIG = {"bridgeid", "mac", "panid"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    diag: dict[str, Any] = {}

    diag["config"] = async_redact_data(config_entry.as_dict(), REDACT_CONFIG)
    diag["deconz_config"] = async_redact_data(
        gateway.api.config.raw, REDACT_DECONZ_CONFIG
    )
    diag["websocket_state"] = (
        gateway.api.websocket.state.value if gateway.api.websocket else "Unknown"
    )
    diag["deconz_ids"] = gateway.deconz_ids
    diag["entities"] = gateway.entities
    diag["events"] = {
        event.serial: {
            "event_id": event.event_id,
            "event_type": type(event).__name__,
        }
        for event in gateway.events
    }
    diag["alarm_systems"] = {k: v.raw for k, v in gateway.api.alarm_systems.items()}
    diag["groups"] = {k: v.raw for k, v in gateway.api.groups.items()}
    diag["lights"] = {k: v.raw for k, v in gateway.api.lights.items()}
    diag["scenes"] = {k: v.raw for k, v in gateway.api.scenes.items()}
    diag["sensors"] = {k: v.raw for k, v in gateway.api.sensors.items()}

    return diag
