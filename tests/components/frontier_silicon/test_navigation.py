"""Test Frontier Silicon media navigation."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from afsapi import FSApiError, PlayerMode
import pytest

from homeassistant.components.frontier_silicon.media_player import AFSAPIMediaPlayer
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DATA_COMPONENT,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    BrowseError,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

ENTITY_ID = "media_player.name_of_the_device"


@pytest.mark.parametrize(
    ("media_id", "command", "args"),
    [
        pytest.param(
            "MockedMode/channels/1/2",
            "nav_select_item_via_path",
            ["1", "2"],
            id="channel",
        ),
        pytest.param("MockedMode/preset/1", "select_preset", 0, id="preset"),
    ],
)
async def test_play_media_preserves_active_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
    media_id: str,
    command: str,
    args: list[str] | int,
) -> None:
    """Playing in the active mode must not clear the API navigation cache."""
    mock_afsapi.get_power.return_value = True
    await setup_integration(hass, config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
            ATTR_MEDIA_CONTENT_ID: media_id,
        },
        blocking=True,
    )

    mock_afsapi.set_power.assert_awaited_once_with(True)
    mock_afsapi.set_mode.assert_not_awaited()
    getattr(mock_afsapi, command).assert_awaited_once_with(args)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_CONTENT_ID] == media_id


async def test_channels_root_resets_navigation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Reopening Channels returns the root, not the last played station's folder."""
    mock_afsapi.get_power.return_value = True
    mock_afsapi.nav_list.return_value.__aiter__.return_value = [
        ("1", {"label": "Locations", "type": "0"})
    ]
    await setup_integration(hass, config_entry)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": MediaType.CHANNELS,
            "media_content_id": "MockedMode/channels",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["children"][0]["title"] == "Locations"
    mock_afsapi.nav_reset.assert_awaited_once_with()
    mock_afsapi.nav_select_folder_via_path.assert_not_awaited()
    mock_afsapi.set_mode.assert_not_awaited()
    mock_afsapi.set_power.assert_not_awaited()
    mock_afsapi.nav_select_item_via_path.assert_not_awaited()


@pytest.mark.parametrize(
    ("first_method", "second_method"),
    [
        pytest.param("async_browse_media", "async_browse_media", id="browse-browse"),
        pytest.param("async_browse_media", "async_play_media", id="browse-play"),
        pytest.param("async_play_media", "async_browse_media", id="play-browse"),
        pytest.param("async_play_media", "async_play_media", id="play-play"),
        pytest.param("async_browse_media", "async_select_source", id="browse-source"),
        pytest.param("async_select_source", "async_browse_media", id="source-browse"),
        pytest.param("async_play_media", "async_select_source", id="play-source"),
        pytest.param("async_select_source", "async_play_media", id="source-play"),
        pytest.param("async_select_source", "async_select_source", id="source-source"),
    ],
)
async def test_navigation_is_serialized(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
    first_method: str,
    second_method: str,
) -> None:
    """A second request cannot navigate until the first finishes listing or playing."""
    mock_afsapi.get_power.return_value = True
    await setup_integration(hass, config_entry)
    entity = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert isinstance(entity, AFSAPIMediaPlayer)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold_play(keys: list[str]) -> None:
        entered.set()
        await release.wait()

    async def hold_list() -> AsyncGenerator[tuple[str, dict[str, str]]]:
        entered.set()
        await release.wait()
        yield "2", {"label": "Station", "type": "1"}

    mock_afsapi.nav_select_item_via_path.side_effect = hold_play
    mock_afsapi.set_mode.side_effect = hold_play
    mock_afsapi.nav_list.side_effect = hold_list
    request_args = {
        "async_browse_media": (MediaType.CHANNEL, "MockedMode/channels/1"),
        "async_play_media": (MediaType.CHANNEL, "MockedMode/channels/1"),
        "async_select_source": ("MockedMode",),
    }
    first = asyncio.create_task(
        getattr(entity, first_method)(*request_args[first_method])
    )
    await entered.wait()
    mock_afsapi.reset_mock()
    second = asyncio.create_task(
        getattr(entity, second_method)(*request_args[second_method])
    )
    try:
        # Let the second task run up to its first blocking await.
        await asyncio.sleep(0)
        assert mock_afsapi.mock_calls == []
    finally:
        release.set()
        await asyncio.gather(first, second)


@pytest.mark.parametrize("powered_on", [True, False])
async def test_play_media_selects_other_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
    powered_on: bool,
) -> None:
    """Changing source and powering on still work when playing a channel."""
    mock_afsapi.get_power.return_value = powered_on
    mock_afsapi.get_mode.return_value = PlayerMode(
        id="other",
        key=1,
        label="Other mode",
        selectable=True,
        streamable=None,
        modetype=None,
    )
    await setup_integration(hass, config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
            ATTR_MEDIA_CONTENT_ID: "MockedMode/channels/1/2",
        },
        blocking=True,
    )

    mock_afsapi.set_power.assert_awaited_once_with(True)
    mock_afsapi.set_mode.assert_awaited_once_with(0)
    mock_afsapi.nav_select_item_via_path.assert_awaited_once_with(["1", "2"])


@pytest.mark.parametrize(
    ("media_id", "command", "args"),
    [
        pytest.param(
            "MockedMode/channels/1/2",
            "nav_select_folder_via_path",
            (["1", "2"],),
            id="folder",
        ),
        pytest.param("MockedMode/preset", "get_presets", (), id="presets"),
    ],
)
async def test_browse_does_not_reset_other_directories(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
    media_id: str,
    command: str,
    args: tuple[list[str], ...],
) -> None:
    """Only opening the Channels root explicitly resets device navigation."""
    await setup_integration(hass, config_entry)
    entity = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert isinstance(entity, AFSAPIMediaPlayer)

    result = await entity.async_browse_media(MediaType.CHANNELS, media_id)

    assert result.media_content_id == media_id
    getattr(mock_afsapi, command).assert_awaited_once_with(*args)
    mock_afsapi.nav_reset.assert_not_awaited()
    mock_afsapi.set_mode.assert_not_awaited()
    mock_afsapi.set_power.assert_not_awaited()


async def test_navigation_lock_released_after_browse_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
) -> None:
    """An API failure must not leave subsequent browsing blocked."""
    await setup_integration(hass, config_entry)
    entity = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert isinstance(entity, AFSAPIMediaPlayer)
    mock_afsapi.nav_reset.side_effect = [FSApiError("Navigation failed"), None]

    with pytest.raises(BrowseError, match="Navigation failed"):
        await entity.async_browse_media(MediaType.CHANNELS, "MockedMode/channels")

    async with asyncio.timeout(1):
        result = await entity.async_browse_media(
            MediaType.CHANNELS, "MockedMode/channels"
        )
    assert result.media_content_id == "MockedMode/channels"
    assert mock_afsapi.nav_reset.await_count == 2


@pytest.mark.parametrize(
    ("cached_label", "live_label", "mode_changes"),
    [
        pytest.param("MockedMode", "Other mode", 1, id="cached-requested-live-other"),
        pytest.param("Other mode", "MockedMode", 0, id="cached-other-live-requested"),
    ],
)
@pytest.mark.parametrize("media_id", ["MockedMode/channels/1/2", "MockedMode/preset/1"])
async def test_play_media_checks_live_mode_after_power_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
    cached_label: str,
    live_label: str,
    mode_changes: int,
    media_id: str,
) -> None:
    """Use the device mode even if the physical source changed since the last poll."""
    mock_afsapi.get_power.return_value = True
    mock_afsapi.get_mode.return_value = PlayerMode(
        id="cached",
        key=0,
        label=cached_label,
        selectable=True,
        streamable=None,
        modetype=None,
    )
    await setup_integration(hass, config_entry)
    entity = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert isinstance(entity, AFSAPIMediaPlayer)
    assert entity.source == cached_label
    mock_afsapi.reset_mock()

    async def live_mode() -> PlayerMode:
        mock_afsapi.set_power.assert_awaited_once_with(True)
        mock_afsapi.set_mode.assert_not_awaited()
        mock_afsapi.nav_select_item_via_path.assert_not_awaited()
        mock_afsapi.select_preset.assert_not_awaited()
        return PlayerMode(
            id="live",
            key=0,
            label=live_label,
            selectable=True,
            streamable=None,
            modetype=None,
        )

    mock_afsapi.get_mode.side_effect = live_mode
    # Isolate the decision read from the subsequent refresh's own mode read.
    with patch.object(entity, "async_update"):
        await entity.async_play_media(MediaType.CHANNEL, media_id)

    assert mock_afsapi.set_mode.await_count == mode_changes
    mock_afsapi.get_mode.assert_awaited_once_with()
