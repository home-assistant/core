"""Tests for Plex buttons."""
from unittest.mock import patch

from homeassistant.components.plex.button import CLIENT_SCAN_INTERVAL
from homeassistant.util import dt

from tests.common import async_fire_time_changed


async def test_scan_clients_button_schedule(hass, setup_plex_server):
    """Test scan_clients button scheduled update."""
    with patch(
        "homeassistant.components.plex.server.PlexServer._async_update_platforms"
    ) as mock_scan_clients:
        await setup_plex_server()
        mock_scan_clients.reset_mock()

        async_fire_time_changed(
            hass,
            dt.utcnow() + CLIENT_SCAN_INTERVAL,
        )
        await hass.async_block_till_done()

    assert mock_scan_clients.called
