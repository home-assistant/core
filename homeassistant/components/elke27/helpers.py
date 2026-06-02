"""Shared entity helpers for the Elke27 integration."""

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


def device_info_for_entry(
    hub: Elke27Hub,
    coordinator: Elke27DataUpdateCoordinator,
    entry: Elke27ConfigEntry,
) -> DeviceInfo:
    """Build device info for entities tied to a config entry."""
    snapshot = coordinator.data
    panel_info = snapshot.panel
    panel_name = hub.panel_name or entry.title
    try:
        formatted_mac = format_mac(str(panel_info.mac)) if panel_info.mac else None
    except ValueError:
        formatted_mac = None
    identifier = unique_base(entry)
    identifiers = {(DOMAIN, identifier)}
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, formatted_mac)}
        if formatted_mac
        else set(),
        identifiers=identifiers,
        name=panel_name,
        model=panel_info.model,
        sw_version=panel_info.firmware,
        serial_number=panel_info.serial,
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
