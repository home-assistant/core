"""Diagnostics support for Speedtest.net."""

from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_SERVER_ID, DEFAULT_SERVER
from .coordinator import SpeedTestConfigEntry

# Client info (IP, ISP, location) and server location/host are left out on purpose
RESULT_KEYS = ("download", "upload", "ping", "bytes_sent", "bytes_received")
SERVER_KEYS = ("id", "sponsor", "country", "cc", "latency")


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SpeedTestConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    results: dict[str, Any] | None = None
    if data := coordinator.data:
        results = {key: data[key] for key in RESULT_KEYS if key in data}
        results["server"] = {
            key: value
            for key, value in data.get("server", {}).items()
            if key in SERVER_KEYS
        }
    return {
        "configured_server_id": entry.options.get(CONF_SERVER_ID),
        "last_update_success": coordinator.last_update_success,
        "known_servers": len(coordinator.servers.keys() - {DEFAULT_SERVER}),
        "results": results,
    }
