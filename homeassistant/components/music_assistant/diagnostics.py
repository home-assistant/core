"""Diagnostics support for Music Assistant."""

from typing import TYPE_CHECKING, Any

from music_assistant_models.constants import (
    PLAYER_CONTROL_FAKE,
    PLAYER_CONTROL_NATIVE,
    PLAYER_CONTROL_NONE,
)
from music_assistant_models.player import Player
from music_assistant_models.player_queue import PlayerQueue

from homeassistant.core import HomeAssistant

from . import MusicAssistantConfigEntry

# Player ids are often derived from MAC addresses or other unique identifiers,
# so they are left out together with every field that references them.
PLAYER_KEYS = (
    "provider",
    "type",
    "name",
    "available",
    "enabled",
    "expose_to_ha",
    "playback_state",
    "powered",
    "volume_level",
    "volume_muted",
    "group_volume",
    "group_volume_muted",
    "active_sound_mode",
    "needs_setup",
    "setup_reason",
)
DEVICE_INFO_KEYS = ("model", "model_id", "manufacturer", "software_version")
SOURCE_KEYS = (
    "name",
    "passive",
    "can_play_pause",
    "can_seek",
    "can_next_previous",
    "can_shuffle",
    "can_repeat",
)
OPTION_KEYS = ("key", "type", "read_only", "value")
CONTROL_KEYS = ("power_control", "volume_control", "mute_control")
BUILTIN_CONTROLS = {PLAYER_CONTROL_NATIVE, PLAYER_CONTROL_NONE, PLAYER_CONTROL_FAKE}
QUEUE_KEYS = (
    "active",
    "available",
    "state",
    "items",
    "shuffle_enabled",
    "repeat_mode",
    "crossfade_enabled",
    "autoplay_enabled",
    "flow_mode",
    "playback_speed",
)


def _player_diagnostics(player: Player, queue: PlayerQueue | None) -> dict[str, Any]:
    """Return diagnostics for a player."""
    data = player.to_dict()
    active_source = next(
        (
            source["name"]
            for source in data["source_list"]
            if source["id"] == data["active_source"]
        ),
        None,
    )
    queue_data = queue.to_dict() if queue else None
    return {
        **{key: data[key] for key in PLAYER_KEYS},
        # Controls can be delegated to another player, referenced by its player id
        **{
            key: data[key] if data[key] in BUILTIN_CONTROLS else "delegated"
            for key in CONTROL_KEYS
        },
        "device_info": {key: data["device_info"][key] for key in DEVICE_INFO_KEYS},
        "supported_features": sorted(data["supported_features"]),
        "group_member_count": len(data["group_members"]),
        "is_synced": data["synced_to"] is not None,
        "active_source": active_source,
        "sources": [
            {key: source[key] for key in SOURCE_KEYS} for source in data["source_list"]
        ],
        "sound_modes": [mode["id"] for mode in data["sound_mode_list"]],
        "options": [
            {key: option[key] for key in OPTION_KEYS} for option in data["options"]
        ],
        "queue": {key: queue_data[key] for key in QUEUE_KEYS} if queue_data else None,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MusicAssistantConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    mass = entry.runtime_data.mass
    server_info = mass.server_info
    if TYPE_CHECKING:
        assert server_info is not None
    return {
        "server_info": {
            "server_version": server_info.server_version,
            "schema_version": server_info.schema_version,
            "min_supported_schema_version": server_info.min_supported_schema_version,
            "homeassistant_addon": server_info.homeassistant_addon,
            "onboard_done": server_info.onboard_done,
        },
        "connected": mass.connection.connected,
        "players": [
            _player_diagnostics(player, mass.player_queues.get(player.player_id))
            for player in mass.players
        ],
    }
