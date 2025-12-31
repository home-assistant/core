"""Shared entity helpers for the Elke27 integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .hub import Elke27Hub


def get_panel_field(hub: Elke27Hub, field: str) -> Any:
    """Return a field from the current panel snapshot."""
    panel_info = hub.panel_info
    if isinstance(panel_info, dict):
        return panel_info.get(field)
    return getattr(panel_info, field, None)


def device_info_for_entry(hub: Elke27Hub, entry: ConfigEntry) -> DeviceInfo:
    """Build device info for entities tied to a config entry."""
    panel_name = get_panel_field(hub, "panel_name") or entry.title
    mac = get_panel_field(hub, "panel_mac")
    identifiers = {(DOMAIN, mac)} if mac else {(DOMAIN, entry.entry_id)}
    return DeviceInfo(identifiers=identifiers, name=panel_name)


def unique_base(hub: Elke27Hub, entry: ConfigEntry) -> str:
    """Return the stable unique ID base for this config entry."""
    mac = get_panel_field(hub, "panel_mac")
    if mac:
        return str(mac)
    if entry.unique_id:
        return entry.unique_id
    return entry.data[CONF_HOST]
