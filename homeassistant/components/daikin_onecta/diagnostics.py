"""Diagnostics support for Daikin Onecta."""

from hashlib import sha256
import secrets
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import DaikinOnectaConfigEntry

TO_REDACT = {
    "access_token",
    "countryCode",
    "country_code",
    "discovery_keys",
    "embeddedId",
    "embedded_id",
    "entry_id",
    "gatewayDevices",
    "gateway_device_ids",
    "id",
    "ipAddress",
    "latitude",
    "longitude",
    "macAddress",
    "mac_address",
    "name",
    "placeID",
    "place_id",
    "refresh_token",
    "serialNumber",
    "serial_number",
    "sgtin",
    "ssid",
    "token",
    "title",
    "unique_id",
    "users",
    "wifiConnectionSSID",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: DaikinOnectaConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics with account Sites context."""
    coordinator = entry.runtime_data
    site_lookup = await coordinator.async_get_site_lookup(use_cache=True)
    if (err := site_lookup.error) is not None:
        site_diagnostics: dict[str, Any] = {
            "error": {
                "type": type(err).__name__,
                "status": getattr(err, "status", None),
            }
        }
    else:
        salt = secrets.token_bytes(16)
        site_diagnostics = {
            "data": [site.to_dict() for site in site_lookup.sites],
            "gateway_membership": [
                {
                    "gateway_id_hash": sha256(salt + device.id.encode()).hexdigest()[
                        :8
                    ],
                    "linked_to_site": site_lookup.gateway_membership(device.id),
                }
                for device in (coordinator.data or {}).values()
            ],
        }

    return async_redact_data(
        {
            "config_entry": entry.as_dict(),
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "rate_limits": coordinator.rate_limits,
            },
            "sites": site_diagnostics,
            "devices": [
                device.device.to_dict() for device in (coordinator.data or {}).values()
            ],
        },
        TO_REDACT,
    )
