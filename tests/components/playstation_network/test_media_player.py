"""Test the Playstation Network media player platform."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def media_player_only() -> AsyncGenerator[None]:
    """Enable only the media_player platform."""
    with patch(
        "homeassistant.components.playstation_network.PLATFORMS",
        [Platform.MEDIA_PLAYER],
    ):
        yield


@pytest.mark.parametrize(
    "presence_payload",
    [
        {
            "basicPresence": {
                "availability": "availableToPlay",
                "primaryPlatformInfo": {"onlineStatus": "online", "platform": "PS5"},
                "gameTitleInfoList": [
                    {
                        "npTitleId": "PPSA07784_00",
                        "titleName": "STAR WARS Jedi: Survivor™",
                        "format": "PS5",
                        "launchPlatform": "PS5",
                        "conceptIconUrl": "https://image.api.playstation.com/vulcan/ap/rnd/202211/2222/l8QTN7ThQK3lRBHhB3nX1s7h.png",
                    }
                ],
            }
        },
        {
            "basicPresence": {
                "availability": "availableToPlay",
                "primaryPlatformInfo": {"onlineStatus": "online", "platform": "PS4"},
                "gameTitleInfoList": [
                    {
                        "npTitleId": "CUSA23081_00",
                        "titleName": "Untitled Goose Game",
                        "format": "PS4",
                        "launchPlatform": "PS4",
                        "npTitleIconUrl": "http://gs2-sec.ww.prod.dl.playstation.net/gs2-sec/appkgo/prod/CUSA23081_00/5/i_f5d2adec7665af80b8550fb33fe808df10d292cdd47629a991debfdf72bdee34/i/icon0.png",
                    }
                ],
            }
        },
        {
            "basicPresence": {
                "availability": "unavailable",
                "lastAvailableDate": "2025-05-02T17:47:59.392Z",
                "primaryPlatformInfo": {
                    "onlineStatus": "offline",
                    "platform": "PS5",
                    "lastOnlineDate": "2025-05-02T17:47:59.392Z",
                },
            }
        },
        {
            "basicPresence": {
                "availability": "unavailable",
                "lastAvailableDate": "2025-05-02T17:47:59.392Z",
                "primaryPlatformInfo": {
                    "onlineStatus": "offline",
                    "platform": "PS4",
                    "lastOnlineDate": "2025-05-02T17:47:59.392Z",
                },
            }
        },
        {
            "basicPresence": {
                "availability": "availableToPlay",
                "primaryPlatformInfo": {"onlineStatus": "online", "platform": "PS5"},
            }
        },
        {
            "basicPresence": {
                "availability": "availableToPlay",
                "primaryPlatformInfo": {"onlineStatus": "online", "platform": "PS4"},
            }
        },
    ],
    ids=[
        "PS5_playing",
        "PS4_playing",
        "PS5_offline",
        "PS4_offline",
        "PS5_idle",
        "PS4_idle",
    ],
)
@pytest.mark.usefixtures("mock_psnawpapi", "mock_token")
async def test_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_psnawpapi: MagicMock,
    presence_payload: dict[str, Any],
) -> None:
    """Test setup of the PlayStation Network media_player platform."""

    mock_psnawpapi.user().get_presence.return_value = presence_payload
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
