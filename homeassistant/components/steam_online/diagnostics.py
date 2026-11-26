"""Diagnostics support for the Steam integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from .const import SUBENTRY_TYPE_FRIEND
from .coordinator import SteamConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SteamConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # The API key, Steam IDs, persona and real names, profile and avatar URLs,
    # location, clan, lobby and game server details are left out, as they
    # identify the account owner and their friends. Players are emitted as a
    # list instead of a dict keyed by Steam ID for the same reason.
    return {
        "last_update_success": coordinator.last_update_success,
        "friends_configured": len(entry.get_subentries_of_type(SUBENTRY_TYPE_FRIEND)),
        "players_returned": len(coordinator.data),
        "game_icons_cached": len(coordinator.game_icons),
        "players": [
            {
                "is_config_entry_account": player.steamid == entry.unique_id,
                "community_visibility_state": player.communityvisibilitystate,
                "profile_state": player.profilestate,
                "persona_state": player.personastate,
                "persona_state_flags": player.personastateflags,
                "level": player.level,
                "has_last_logoff": player.lastlogoff is not None,
                "in_game": player.gameid is not None,
                "has_game_icon": (
                    player.gameid is not None
                    and player.gameid in coordinator.game_icons
                ),
            }
            for player in coordinator.data.values()
        ],
    }
