"""Tests for Plex buttons."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.plex.const import DEBOUNCE_TIMEOUT
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_scan_clients_button_schedule(
    hass: HomeAssistant, setup_plex_server
) -> None:
    """Test scan_clients button scheduled update."""
    with patch(
        "homeassistant.components.plex.server.PlexServer._async_update_platforms"
    ) as mock_scan_clients:
        await setup_plex_server()
        mock_scan_clients.reset_mock()

        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=DEBOUNCE_TIMEOUT),
        )

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.plex_server_1_scan_clients",
            },
            True,
        )
        await hass.async_block_till_done()

    assert mock_scan_clients.called
