"""Tests for various Plex services."""
from homeassistant.components.plex.const import (
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DOMAIN,
    PLEX_SERVER_CONFIG,
    SERVICE_REFRESH_LIBRARY,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
)

from .const import DEFAULT_DATA, DEFAULT_OPTIONS, MOCK_SERVERS, MOCK_TOKEN
from .mock_classes import MockPlexAccount, MockPlexLibrarySection, MockPlexServer

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_refresh_library(hass):
    """Test refresh_library service call."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch("homeassistant.components.plex.PlexWebsocket", autospec=True):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Test with non-existent server
    with patch.object(MockPlexLibrarySection, "update") as mock_update:
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"server_name": "Not a Server", "library_name": "Movies"},
            True,
        )
        assert not mock_update.called

    # Test with non-existent library
    with patch.object(MockPlexLibrarySection, "update") as mock_update:
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"library_name": "Not a Library"},
            True,
        )
        assert not mock_update.called

    # Test with valid library
    with patch.object(MockPlexLibrarySection, "update") as mock_update:
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"library_name": "Movies"},
            True,
        )
        assert mock_update.called

    # Add a second configured server
    entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERVER: MOCK_SERVERS[1][CONF_SERVER],
            PLEX_SERVER_CONFIG: {
                CONF_TOKEN: MOCK_TOKEN,
                CONF_URL: f"https://{MOCK_SERVERS[1][CONF_HOST]}:{MOCK_SERVERS[1][CONF_PORT]}",
                CONF_VERIFY_SSL: True,
            },
            CONF_SERVER_IDENTIFIER: MOCK_SERVERS[1][CONF_SERVER_IDENTIFIER],
        },
    )

    mock_plex_server_2 = MockPlexServer(config_entry=entry_2)
    with patch("plexapi.server.PlexServer", return_value=mock_plex_server_2), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch("homeassistant.components.plex.PlexWebsocket", autospec=True):
        entry_2.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry_2.entry_id)
        await hass.async_block_till_done()

    # Test multiple servers available but none specified
    with patch.object(MockPlexLibrarySection, "update") as mock_update:
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"library_name": "Movies"},
            True,
        )
        assert not mock_update.called
