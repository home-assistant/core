"""Diagnostics support for Elke27."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_LINK_KEYS, DOMAIN
from .hub import Elke27Hub

TO_REDACT = {
    CONF_LINK_KEYS,
    "link_keys",
    "panel_mac",
    "panel_serial",
    "panel_host",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub: Elke27Hub | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    panel_info = entry.options.get("panel_info") or getattr(hub, "panel_info", None)
    table_info = entry.options.get("table_info") or getattr(hub, "table_info", None)
    ready = bool(hub and hub.is_ready)

    panel_info = _as_dict(panel_info)
    table_info = _as_dict(table_info)

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "entry_options": async_redact_data(entry.options, TO_REDACT),
        "panel_info": async_redact_data(panel_info, TO_REDACT),
        "table_info": async_redact_data(table_info, TO_REDACT),
        "ready": ready,
    }


def _as_dict(value: Any) -> dict[str, Any]:
    """Normalize snapshots to dict."""
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return {"value": value}
