"""Diagnostics support for Cloudflare."""

from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_RECORDS
from .coordinator import CloudflareConfigEntry

# The integration only looks up and updates A records.
MANAGED_RECORD_TYPES = ["A"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CloudflareConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    zone = coordinator.zone
    zone_meta = zone.get("meta", {})

    # The API token, zone name and ID, account, record names and IP addresses
    # are left out, as they are credentials or identify the user. The
    # coordinator does not keep the records it fetches, so only the number of
    # configured records is reported.
    return {
        "config_entry": {
            "managed_records": len(entry.data[CONF_RECORDS]),
            "managed_record_types": MANAGED_RECORD_TYPES,
        },
        "zone": {
            "development_mode": zone.get("development_mode"),
            "dns_only": zone_meta.get("dns_only"),
            "cdn_only": zone_meta.get("cdn_only"),
            "foundation_dns": zone_meta.get("foundation_dns"),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                type(coordinator.last_exception).__name__
                if coordinator.last_exception
                else None
            ),
            "update_interval": str(coordinator.update_interval),
        },
    }
