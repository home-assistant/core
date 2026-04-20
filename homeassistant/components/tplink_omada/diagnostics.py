"""Diagnostics support for TP-Link Omada."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from . import OmadaConfigEntry

ENTRY_TO_REDACT = {
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
}

RUNTIME_TO_REDACT = {
    "addr",
    "echoServer",
    "gateway",
    "gateway2",
    "hostName",
    "ip",
    "priDns",
    "priDns2",
    "sndDns",
    "sndDns2",
    "ssid",
    "sn",
    "omadacId",
}


def _build_identifier_replacements(mac_values: set[str]) -> dict[str, str]:
    """Build deterministic replacement values for network identifiers."""
    replacements: dict[str, str] = {}

    for index, raw_mac in enumerate(sorted(mac_values)):
        pseudonym = format_mac(str(index).zfill(12))
        variants = {raw_mac, raw_mac.upper(), raw_mac.lower()}

        normalized = format_mac(raw_mac)
        variants.update({normalized, normalized.upper(), normalized.lower()})

        for variant in variants:
            replacements[variant] = pseudonym

    return replacements


def _replace_identifiers(data: Any, to_replace: Mapping[str, str]) -> Any:
    """Replace network identifiers in nested diagnostics payloads."""
    if isinstance(data, Mapping):
        return {
            key: _replace_identifiers(value, to_replace) for key, value in data.items()
        }

    if isinstance(data, list):
        return [_replace_identifiers(item, to_replace) for item in data]

    if isinstance(data, str):
        return to_replace.get(data, data)

    return data


def _redact_runtime_record(
    raw_data: Mapping[str, Any], replacements: Mapping[str, str]
) -> dict[str, Any]:
    """Apply identifier replacement and key redaction to runtime data."""
    return async_redact_data(
        _replace_identifiers(raw_data, replacements),
        RUNTIME_TO_REDACT,
    )


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OmadaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = entry.runtime_data

    devices = controller.devices_coordinator.data
    clients = controller.clients_coordinator.data

    gateway_data: dict[str, Any] | None = None
    if (
        gateway_coordinator := controller.gateway_coordinator
    ) and gateway_coordinator.data:
        gateway = next(iter(gateway_coordinator.data.values()))
        gateway_data = gateway.raw_data

    mac_values = set(devices) | set(clients)
    for client in clients.values():
        if ap_mac := client.raw_data.get("apMac"):
            mac_values.add(ap_mac)
    if gateway_data and (gateway_mac := gateway_data.get("mac")):
        mac_values.add(gateway_mac)

    replacements = _build_identifier_replacements(mac_values)

    return {
        "entry": async_redact_data(entry.as_dict(), ENTRY_TO_REDACT),
        "runtime": {
            "devices": {
                replacements[mac]: _redact_runtime_record(
                    device.raw_data,
                    replacements,
                )
                for mac, device in devices.items()
            },
            "clients": {
                replacements[mac]: _redact_runtime_record(
                    client.raw_data,
                    replacements,
                )
                for mac, client in clients.items()
            },
            "gateway": (
                _redact_runtime_record(gateway_data, replacements)
                if gateway_data is not None
                else None
            ),
        },
    }
