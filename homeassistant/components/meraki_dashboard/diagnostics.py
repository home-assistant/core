"""Diagnostics support for Meraki Dashboard."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import MerakiDashboardConfigEntry

TO_REDACT = {
    CONF_API_KEY,
    "ip",
    "ip6",
    "ip_address",
    "ip6_address",
    "mac",
    "public_ip",
    "lan_ip",
    "gateway",
    "primary_dns",
    "secondary_dns",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MerakiDashboardConfigEntry
) -> dict[str, object]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    clients = {mac: asdict(client) for mac, client in coordinator.data.clients.items()}
    infrastructure_devices = {
        serial: asdict(device)
        for serial, device in coordinator.data.infrastructure_devices.items()
    }

    return async_redact_data(
        {
            "config_entry": config_entry.as_dict(),
            "coordinator": {
                "network_id": coordinator.network_id,
                "organization_id": coordinator.organization_id,
                "track_clients": coordinator.track_clients,
                "track_infrastructure_devices": (
                    coordinator.track_infrastructure_devices
                ),
                "included_clients": sorted(coordinator.included_clients),
            },
            "clients_count": len(clients),
            "infrastructure_devices_count": len(infrastructure_devices),
            "clients": clients,
            "infrastructure_devices": infrastructure_devices,
        },
        TO_REDACT,
    )
