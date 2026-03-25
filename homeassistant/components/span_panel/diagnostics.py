"""Diagnostics support for the Span Panel integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from . import SpanPanelConfigEntry
from .const import (
    CONF_EBUS_BROKER_PASSWORD,
    CONF_EBUS_BROKER_USERNAME,
    CONF_HOP_PASSPHRASE,
)

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_EBUS_BROKER_PASSWORD,
    CONF_EBUS_BROKER_USERNAME,
    CONF_HOP_PASSPHRASE,
    "password",
    "username",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: SpanPanelConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    snapshot = coordinator.data

    panel_data: dict[str, Any] = {
        "serial_number": snapshot.serial_number,
        "firmware_version": snapshot.firmware_version,
        "panel_size": snapshot.panel_size,
    }

    if snapshot.wifi_ssid is not None:
        panel_data["wifi_ssid"] = snapshot.wifi_ssid
    if snapshot.eth0_link is not None:
        panel_data["eth0_link"] = snapshot.eth0_link
    if snapshot.wlan_link is not None:
        panel_data["wlan_link"] = snapshot.wlan_link

    circuit_data: dict[str, dict[str, Any]] = {}
    for circuit_id, circuit in snapshot.circuits.items():
        circuit_data[circuit_id] = {
            "name": circuit.name,
            "relay_state": circuit.relay_state,
            "priority": circuit.priority,
            "is_user_controllable": circuit.is_user_controllable,
            "instant_power_w": circuit.instant_power_w,
            "produced_energy_wh": circuit.produced_energy_wh,
            "consumed_energy_wh": circuit.consumed_energy_wh,
        }
        if hasattr(circuit, "device_type"):
            circuit_data[circuit_id]["device_type"] = circuit.device_type
        if hasattr(circuit, "tabs"):
            circuit_data[circuit_id]["tabs"] = circuit.tabs

    evse_data: dict[str, dict[str, Any]] = {}
    if snapshot.evse:
        for evse_id, evse in snapshot.evse.items():
            evse_data[evse_id] = {
                "node_id": evse.node_id,
                "feed_circuit_id": evse.feed_circuit_id,
                "status": evse.status,
                "lock_state": evse.lock_state,
                "advertised_current_a": evse.advertised_current_a,
            }

    battery_data: dict[str, Any] = {}
    if snapshot.battery:
        battery_data = {
            "connected": snapshot.battery.connected,
            "soe_percentage": snapshot.battery.soe_percentage,
            "soe_kwh": snapshot.battery.soe_kwh,
        }

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "panel": panel_data,
        "circuits": circuit_data,
        "evse": evse_data,
        "battery": battery_data,
        "coordinator": {
            "panel_offline": coordinator.panel_offline,
            "last_update_success": coordinator.last_update_success,
        },
    }
