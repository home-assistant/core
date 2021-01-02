"""Tests for various Plex services."""
from unittest.mock import patch

from homeassistant.components.plex.const import (
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DOMAIN,
    PLEX_SERVER_CONFIG,
    SERVICE_REFRESH_LIBRARY,
    SERVICE_SCAN_CLIENTS,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
)

from .const import MOCK_SERVERS, MOCK_TOKEN
from .mock_classes import MockPlexLibrarySection

from tests.common import MockConfigEntry


async def test_refresh_library(hass, mock_plex_server, setup_plex_server):
    """Test refresh_library service call."""
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

    await setup_plex_server(config_entry=entry_2)

    # Test multiple servers available but none specified
    with patch.object(MockPlexLibrarySection, "update") as mock_update:
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"library_name": "Movies"},
            True,
        )
        assert not mock_update.called


async def test_scan_clients(hass, mock_plex_server):
    """Test scan_for_clients service call."""
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SCAN_CLIENTS,
        blocking=True,
    )
