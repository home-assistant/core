"""Test Control4 Media Player."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.control4.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_media_player_with_and_without_sources(hass: HomeAssistant) -> None:
    """Test that rooms with sources create entities and rooms without are skipped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.100",
            "username": "test",
            "password": "test",
            "controller_unique_id": "control4_test_123",
        },
    )
    entry.add_to_hass(hass)

    mock_account = MagicMock()
    mock_account.getAccountBearerToken = AsyncMock()
    mock_account.getAccountControllers = AsyncMock(
        return_value={"href": "https://example.com"}
    )
    mock_account.getDirectorBearerToken = AsyncMock(return_value={"token": "test"})
    mock_account.getControllerOSVersion = AsyncMock(return_value="3.2.0")

    # Room 1 has video source, Room 2 has no sources (thermostat-only room)
    mock_director = MagicMock()
    mock_director.getAllItemInfo = AsyncMock(
        return_value=json.dumps(
            [
                {
                    "id": 1,
                    "typeName": "room",
                    "name": "Living Room",
                    "roomHidden": False,
                },
                {
                    "id": 2,
                    "typeName": "room",
                    "name": "Thermostat Room",
                    "roomHidden": False,
                },
                {"id": 100, "name": "TV"},
            ]
        )
    )
    mock_director.getUiConfiguration = AsyncMock(
        return_value=json.dumps(
            {
                "experiences": [
                    {
                        "room_id": 1,
                        "type": "watch",
                        "sources": {"source": [{"id": 100}]},
                    },
                    # Room 2 has no experiences (thermostat-only)
                ]
            }
        )
    )

    async def mock_update_variables(*args, **kwargs):
        return {
            1: {
                "POWER_STATE": True,
                "CURRENT_VOLUME": 50,
                "IS_MUTED": False,
                "CURRENT_VIDEO_DEVICE": 100,
                "CURRENT MEDIA INFO": {},
                "PLAYING": False,
                "PAUSED": False,
                "STOPPED": False,
            }
        }

    with (
        patch("homeassistant.components.control4.C4Account", return_value=mock_account),
        patch(
            "homeassistant.components.control4.C4Director", return_value=mock_director
        ),
        patch("homeassistant.components.control4.PLATFORMS", ["media_player"]),
        patch(
            "homeassistant.components.control4.media_player.update_variables_for_config_entry",
            new=mock_update_variables,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Only 1 media_player entity should be created (Living Room with sources)
    states = hass.states.async_all("media_player")
    assert len(states) == 1
    assert states[0].name == "Living Room"
