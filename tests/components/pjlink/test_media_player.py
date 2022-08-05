"""The tests for the PJLink Media player platform."""
from unittest.mock import AsyncMock, patch

import homeassistant.components.media_player as mp

# from homeassistant.components.pjlink import media_player as pjlink_mp
# from homeassistant.components.pjlink.const import DOMAIN
from homeassistant.const import (  # ATTR_ENTITY_ID,; ATTR_ENTITY_PICTURE,; ATTR_SUPPORTED_FEATURES,; STATE_PAUSED,; STATE_PLAYING,
    STATE_OFF,
)

# from homeassistant.helpers.discovery import async_load_platform
from homeassistant.setup import async_setup_component

# import pytest


CONFIG = {
    "media_player": {
        "platform": "pjlink",
        "host": "127.0.0.1",
        "name": "Cool Projector",
    }
}
TEST_ENTITY_ID = "media_player.cool_projector"


# @patch("socket.socket")
async def test_turning_off_and_on(hass):
    """Test turn_on and turn_off."""

    file_mock = AsyncMock()
    file_mock.read.return_value = "PJLINK 1"

    mock_socket = AsyncMock()
    mock_socket.settimeout
    mock_socket.connect
    mock_socket.makefile.return_value = file_mock
    mock_socket.close

    with patch("socket.socket", timeout=True, return_value=mock_socket):
        assert await async_setup_component(hass, mp.DOMAIN, CONFIG)
        await hass.async_block_till_done()

        assert mock_socket.call_count == 1

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF
