"""Tests for the System Bridge media player platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.models.media_control import MediaAction, MediaControl

from homeassistant.components.media_player import (
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SHUFFLE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    RepeatMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "media_player.hostname_media"


@pytest.fixture(autouse=True)
def media_player_only() -> Generator[None]:
    """Enable only the media player platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.MEDIA_PLAYER],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_media_player_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the media player platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "service_data", "expected"),
    [
        pytest.param(
            SERVICE_MEDIA_PLAY,
            {},
            MediaControl(action=MediaAction.PLAY.value),
            id="play",
        ),
        pytest.param(
            SERVICE_MEDIA_PAUSE,
            {},
            MediaControl(action=MediaAction.PAUSE.value),
            id="pause",
        ),
        pytest.param(
            SERVICE_MEDIA_STOP,
            {},
            MediaControl(action=MediaAction.STOP.value),
            id="stop",
        ),
        pytest.param(
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {},
            MediaControl(action=MediaAction.PREVIOUS.value),
            id="previous",
        ),
        pytest.param(
            SERVICE_MEDIA_NEXT_TRACK,
            {},
            MediaControl(action=MediaAction.NEXT.value),
            id="next",
        ),
        pytest.param(
            SERVICE_SHUFFLE_SET,
            {ATTR_MEDIA_SHUFFLE: False},
            MediaControl(action=MediaAction.SHUFFLE.value, value=False),
            id="shuffle",
        ),
        pytest.param(
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.OFF},
            MediaControl(action=MediaAction.REPEAT.value, value=0),
            id="repeat_off",
        ),
        pytest.param(
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.ONE},
            MediaControl(action=MediaAction.REPEAT.value, value=1),
            id="repeat_one",
        ),
        pytest.param(
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.ALL},
            MediaControl(action=MediaAction.REPEAT.value, value=2),
            id="repeat_all",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_control(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    service: str,
    service_data: dict[str, Any],
    expected: MediaControl,
) -> None:
    """Test media player actions send the matching media control."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_websocket_client.media_control.assert_awaited_once_with(expected)
