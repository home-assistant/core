"""Diagnostics support for qBittorrent."""

from collections import Counter
from collections.abc import Mapping
from typing import Any, cast

from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from .coordinator import QBittorrentConfigEntry

SERVER_STATE_KEYS = (
    "connection_status",
    "dht_nodes",
    "total_peer_connections",
    "dl_info_speed",
    "up_info_speed",
    "dl_rate_limit",
    "up_rate_limit",
    "dl_info_data",
    "up_info_data",
    "alltime_dl",
    "alltime_ul",
    "global_ratio",
    "free_space_on_disk",
    "use_alt_speed_limits",
    "queueing",
    "refresh_interval",
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: QBittorrentConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    server_state = cast(Mapping[str, Any], data.get("server_state") or {})
    torrents = cast(Mapping[str, Mapping[str, Any]], data.get("torrents") or {})

    # The URL, username and password, external IP addresses, categories,
    # trackers, and anything about individual torrents (names, hashes, paths,
    # magnet links) are left out, as they are private. Only the number of
    # torrents per state is included.
    return {
        "config_entry": {
            CONF_VERIFY_SSL: entry.data[CONF_VERIFY_SSL],
        },
        "last_update_success": coordinator.last_update_success,
        "alt_speed_enabled": coordinator.get_alt_speed_enabled(),
        "server_state": {
            key: server_state[key] for key in SERVER_STATE_KEYS if key in server_state
        },
        "torrents": {
            "total": len(torrents),
            "states": dict(
                sorted(
                    Counter(
                        str(torrent.get("state")) for torrent in torrents.values()
                    ).items()
                )
            ),
        },
    }
