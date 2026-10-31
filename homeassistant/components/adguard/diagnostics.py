"""Diagnostics support for AdGuard Home."""

from typing import Any

from homeassistant.const import CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from .coordinator import AdGuardConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AdGuardConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    state = data.state.data
    statistics = data.statistics.data
    update = data.update.data

    # Addresses, domains, clients and upstreams are left out, as they are private.
    return {
        "config_entry": {
            "source": entry.source,
            CONF_SSL: entry.data[CONF_SSL],
            CONF_VERIFY_SSL: entry.data[CONF_VERIFY_SSL],
        },
        "status": {
            "version": str(state.status.version),
            "supported": state.status.supported,
            "running": state.status.running,
            "language": state.status.language,
            "dhcp_available": state.status.dhcp_available,
            "protection_enabled": state.status.protection_enabled,
            "protection_resumes_in": (
                str(resumes_in)
                if (resumes_in := state.status.protection_resumes_in)
                else None
            ),
        },
        "features": {
            "filtering": {
                "enabled": state.filtering.enabled,
                "update_interval": str(state.filtering.update_interval),
            },
            "parental": state.parental,
            "query_log": {
                "enabled": state.query_log.enabled,
                "retention": str(state.query_log.retention),
                "anonymize_client_ip": state.query_log.anonymize_client_ip,
            },
            "safe_browsing": state.safe_browsing,
            "safe_search": state.safe_search.to_dict(),
        },
        "statistics": {
            "dns_queries": statistics.stats.dns_queries,
            "blocked_filtering": statistics.stats.blocked_filtering,
            "blocked_safebrowsing": statistics.stats.blocked_safebrowsing,
            "blocked_parental": statistics.stats.blocked_parental,
            "enforced_safesearch": statistics.stats.enforced_safesearch,
            "avg_processing_time": str(statistics.stats.avg_processing_time),
            "time_unit": statistics.stats.time_unit,
        },
        "blocklists": [
            {
                "id": blocklist.id,
                "name": blocklist.name,
                "enabled": blocklist.enabled,
                "rules_count": blocklist.rules_count,
                "last_updated": blocklist.last_updated,
            }
            for blocklist in statistics.blocklists
        ],
        "update": {
            "last_update_success": data.update.last_update_success,
            "available": update.to_dict() if update else None,
        },
    }
