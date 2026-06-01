"""Shared entity helpers for the Elke27 integration."""

import re
from typing import Any

from elke27_lib import PanelSnapshot

from homeassistant.const import CONF_CLIENT_ID
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)

from .const import DOMAIN
from .coordinator import Elke27DataUpdateCoordinator
from .hub import Elke27Hub
from .models import Elke27ConfigEntry

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_name(name: str | None) -> str | None:
    """Remove control characters from display names."""
    if name is None:
        return None
    return _CONTROL_CHARS_RE.sub("", name)


def get_panel_field(
    snapshot: PanelSnapshot | None, panel_name: str | None, field: str
) -> Any:
    """Return a configured panel field or a field from the current panel snapshot."""
    if field == "name" and panel_name:
        return sanitize_name(panel_name)
    if snapshot is None:
        return None
    panel_info = snapshot.panel
    if field == "name":
        return sanitize_name(
            getattr(panel_info, "panel_name", None) or getattr(panel_info, "name", None)
        )
    if field == "mac":
        return panel_info.mac
    if field == "serial":
        return panel_info.serial
    if field == "model":
        return panel_info.model
    if field == "firmware":
        return panel_info.firmware
    return None


def device_info_for_entry(
    hub: Elke27Hub,
    coordinator: Elke27DataUpdateCoordinator,
    entry: Elke27ConfigEntry,
) -> DeviceInfo:
    """Build device info for entities tied to a config entry."""
    snapshot = coordinator.data
    panel_name = get_panel_field(snapshot, hub.panel_name, "name") or entry.title
    mac = get_panel_field(snapshot, hub.panel_name, "mac")
    try:
        formatted_mac = format_mac(str(mac)) if mac else None
    except ValueError:
        formatted_mac = None
    panel_serial = get_panel_field(snapshot, hub.panel_name, "serial")
    model = get_panel_field(snapshot, hub.panel_name, "model")
    firmware = get_panel_field(snapshot, hub.panel_name, "firmware")
    identifier = unique_base(entry)
    identifiers = {(DOMAIN, identifier)}
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, formatted_mac)}
        if formatted_mac
        else set(),
        identifiers=identifiers,
        name=panel_name,
        model=model,
        sw_version=firmware,
        serial_number=panel_serial,
    )


def unique_base(entry: Elke27ConfigEntry) -> str:
    """Return the stable unique ID base for this config entry."""
    if entry.unique_id:
        return entry.unique_id
    client_id = entry.data.get(CONF_CLIENT_ID)
    if client_id:
        return str(client_id)
    return entry.entry_id


def build_unique_id(base: str, numeric_id: int | str) -> str:
    """Build a stable unique ID in <base>:<id> format."""
    return f"{base}:{numeric_id}"
