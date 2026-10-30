"""Diagnostics support for Plex."""

from typing import Any

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from .const import CONF_MONITORED_USERS, PLEX_SERVER_CONFIG
from .helpers import PlexConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PlexConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    plex_server = entry.runtime_data.server
    server = plex_server.plex_server

    return {
        "options": {
            key: value
            for key, value in entry.options.get(MP_DOMAIN, {}).items()
            if key != CONF_MONITORED_USERS
        },
        "monitored_users": len(plex_server.monitored_users & plex_server.accounts),
        "server": {
            "version": plex_server.version,
            "platform": server.platform,
            "platform_version": server.platformVersion,
            "has_token": plex_server.has_token,
            "verify_ssl": entry.data[PLEX_SERVER_CONFIG].get(CONF_VERIFY_SSL),
            "accounts": len(plex_server.accounts),
            "my_plex": server.myPlex,
            "my_plex_signin_state": server.myPlexSigninState,
            "my_plex_mapping_state": server.myPlexMappingState,
            "my_plex_subscription": server.myPlexSubscription,
            "transcoder_video": server.transcoderVideo,
            "transcoder_audio": server.transcoderAudio,
        },
        "websocket_state": entry.runtime_data.websocket.state,
        "sessions": [
            {
                "state": session.state,
                "media_content_type": session.media_content_type,
                "media_library_title": session.media_library_title,
                "media_duration": session.media_duration,
                "player_product": session.player.product,
                "player_platform": session.player.platform,
                "player_version": session.player.version,
            }
            for session in list(plex_server.active_sessions.values())
        ],
    }
