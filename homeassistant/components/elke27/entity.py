"""Shared entity helpers for the Elke27 integration."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)

from .const import CONF_INTEGRATION_SERIAL, DOMAIN, MANUFACTURER_NUMBER
from .coordinator import Elke27DataUpdateCoordinator
from .hub import Elke27Hub


_NAME_SAFE_RE = re.compile(r"[^A-Za-z0-9 _-]")


def sanitize_name(name: str | None) -> str | None:
    """Normalize entity names to Home Assistant-safe characters."""
    if name is None:
        return None
    # return _NAME_SAFE_RE.sub("_", name)
    return name


def get_panel_field(
    snapshot: Any | None, panel_name: str | None, field: str
) -> Any:
    """Return a field from the current panel snapshot."""
    if field == "name" and panel_name:
        return sanitize_name(panel_name)
    if snapshot is None:
        return None
    panel_info = getattr(snapshot, "panel_info", None) or getattr(snapshot, "panel", None)
    if panel_info is None:
        return None
    if isinstance(panel_info, dict):
        if field == "name":
            return sanitize_name(panel_info.get("name") or panel_info.get("panel_name"))
        if field == "mac":
            return panel_info.get("mac") or panel_info.get("panel_mac")
        if field == "serial":
            return panel_info.get("serial") or panel_info.get("panel_serial")
        return panel_info.get(field)
    return getattr(panel_info, field, None)


def device_info_for_entry(
    hub: Elke27Hub,
    coordinator: Elke27DataUpdateCoordinator,
    entry: ConfigEntry,
) -> DeviceInfo:
    """Build device info for entities tied to a config entry."""
    snapshot = coordinator.data
    panel_name = get_panel_field(snapshot, hub.panel_name, "name") or entry.title
    mac = get_panel_field(snapshot, hub.panel_name, "mac")
    panel_serial = get_panel_field(snapshot, hub.panel_name, "serial")
    model = get_panel_field(snapshot, hub.panel_name, "model")
    firmware = get_panel_field(snapshot, hub.panel_name, "firmware")
    integration_serial = entry.data.get(CONF_INTEGRATION_SERIAL)
    identifier = (
        f"{MANUFACTURER_NUMBER}-{integration_serial}"
        if integration_serial
        else entry.entry_id
    )
    identifiers = {(DOMAIN, identifier)}
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, mac)} if mac else None,
        identifiers=identifiers,
        name=panel_name,
        model=model,
        sw_version=firmware,
        serial_number=panel_serial,
    )


def unique_base(
    hub: Elke27Hub,
    coordinator: Elke27DataUpdateCoordinator,
    entry: ConfigEntry,
) -> str:
    """Return the stable unique ID base for this config entry."""
    mac = get_panel_field(coordinator.data, hub.panel_name, "mac")
    if mac:
        return format_mac(str(mac))
    integration_serial = entry.data.get(CONF_INTEGRATION_SERIAL)
    if integration_serial:
        return str(integration_serial)
    if entry.unique_id:
        return entry.unique_id
    return entry.data[CONF_HOST]


def build_unique_id(base: str, domain: str, numeric_id: int | str) -> str:
    """Build a stable unique ID in <mac>:<domain>:<id> format."""
    return f"{base}:{domain}:{numeric_id}"
