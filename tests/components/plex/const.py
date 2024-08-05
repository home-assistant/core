"""Constants used by Plex tests."""

from homeassistant.components.plex import const
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    Platform,
)

MOCK_SERVERS = [
    {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 32400,
        const.CONF_SERVER: "Plex Server 1",
        const.CONF_SERVER_IDENTIFIER: "unique_id_123",
    },
    {
        CONF_HOST: "4.3.2.1",
        CONF_PORT: 32400,
        const.CONF_SERVER: "Plex Server 2",
        const.CONF_SERVER_IDENTIFIER: "unique_id_456",
    },
]

MOCK_USERS = {
    "Owner": {"enabled": True},
    "b": {"enabled": True},
    "c": {"enabled": True},
}

MOCK_TOKEN = "secret_token"

DEFAULT_DATA = {
    const.CONF_SERVER: MOCK_SERVERS[0][const.CONF_SERVER],
    const.PLEX_SERVER_CONFIG: {
        CONF_CLIENT_ID: "00000000-0000-0000-0000-000000000000",
        CONF_TOKEN: MOCK_TOKEN,
        CONF_URL: f"https://{MOCK_SERVERS[0][CONF_HOST]}:{MOCK_SERVERS[0][CONF_PORT]}",
        CONF_VERIFY_SSL: True,
    },
    const.CONF_SERVER_IDENTIFIER: MOCK_SERVERS[0][const.CONF_SERVER_IDENTIFIER],
}
SECONDARY_DATA = {
    const.CONF_SERVER: MOCK_SERVERS[1][const.CONF_SERVER],
    const.PLEX_SERVER_CONFIG: {
        CONF_CLIENT_ID: "00000000-0000-0000-0000-000000000002",
        CONF_TOKEN: MOCK_TOKEN,
        CONF_URL: f"https://{MOCK_SERVERS[1][CONF_HOST]}:{MOCK_SERVERS[1][CONF_PORT]}",
        CONF_VERIFY_SSL: True,
    },
    const.CONF_SERVER_IDENTIFIER: MOCK_SERVERS[1][const.CONF_SERVER_IDENTIFIER],
}

DEFAULT_OPTIONS = {
    Platform.MEDIA_PLAYER: {
        const.CONF_IGNORE_NEW_SHARED_USERS: False,
        const.CONF_MONITORED_USERS: MOCK_USERS,
        const.CONF_USE_EPISODE_ART: False,
    }
}

PLEX_DIRECT_URL = "https://1-2-3-4.123456789001234567890.plex.direct:32400"
