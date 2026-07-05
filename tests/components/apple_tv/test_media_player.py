"""Tests for the Apple TV media player."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from pyatv.const import FeatureName, FeatureState, Protocol
from pyatv.exceptions import (
    BlockedStateError,
    ConnectionLostError,
    InvalidStateError,
    NotSupportedError,
    OperationTimeoutError,
    PlaybackError,
    ProtocolError,
)
from pyatv.interface import DeviceInfo, FeatureInfo
import pytest

from homeassistant.components.apple_tv.const import CONF_OUTPUT_DEVICE_ID, DOMAIN
from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_JOIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_UNJOIN,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.components.media_source import PlayMedia
from homeassistant.const import ATTR_ENTITY_ID, CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import create_conf, mrp_service

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

_GROUPING_FEATURES = (
    FeatureName.AddOutputDevices,
    FeatureName.RemoveOutputDevices,
    FeatureName.SetOutputDevices,
)


class _GroupingFeatures:
    """Minimal Features stub advertising only the output-device features.

    Reporting these as available enables the GROUPING entity feature so the
    join/unjoin services target the entity. Everything else is unavailable.
    Kept local so the grouping tests do not depend on the shared conftest
    fixtures.
    """

    def all_features(self) -> dict[FeatureName, FeatureInfo]:
        """Report the output-device features as available."""
        return {
            feature: FeatureInfo(state=FeatureState.Available)
            for feature in _GROUPING_FEATURES
        }

    def in_state(self, states, *features) -> bool:
        """Report that no feature is in the requested state."""
        return False


@pytest.fixture
def create_player(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> Callable[[str], Awaitable[tuple[str, AsyncMock]]]:
    """Set up an Apple TV media player through a real config entry.

    Kept self-contained (no shared conftest fixtures) so upstream changes to
    the shared fixtures do not conflict with these grouping tests.
    """

    async def create(name: str) -> tuple[str, AsyncMock]:
        unique_id = f"{name}-uid"
        output_device_id = f"{name}-output-device-id"

        atv = AsyncMock()
        atv.features = _GroupingFeatures()
        atv.audio.output_devices = []
        atv.device_info.output_device_id = output_device_id
        atv.device_info.mac = f"{name}-mac"

        async def set_output_devices(*devices):
            old_devices = atv.audio.output_devices
            new_devices = [Mock(identifier=ident) for ident in devices]
            atv.audio.output_devices = new_devices
            # Mimic pyatv notifying the AudioListener of the change.
            atv.audio.listener.outputdevices_update(old_devices, new_devices)

        atv.audio.set_output_devices = AsyncMock(side_effect=set_output_devices)
        atv.audio.remove_output_devices = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=unique_id,
            data={
                CONF_ADDRESS: "127.0.0.1",
                CONF_NAME: name,
                CONF_OUTPUT_DEVICE_ID: output_device_id,
                "credentials": {str(Protocol.MRP.value): "mrp_creds"},
                "identifiers": [unique_id],
            },
        )
        entry.add_to_hass(hass)

        device_info = DeviceInfo({DeviceInfo.OUTPUT_DEVICE_ID: output_device_id})
        scan_result = create_conf(
            "127.0.0.1", name, mrp_service(unique_id=unique_id), device_info=device_info
        )

        with (
            patch("homeassistant.components.apple_tv.scan", return_value=[scan_result]),
            patch("homeassistant.components.apple_tv.connect", return_value=atv),
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        entity_id = entity_registry.async_get_entity_id(
            MEDIA_PLAYER_DOMAIN, DOMAIN, unique_id
        )
        assert entity_id is not None
        return entity_id, atv

    return create


def _group_members(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return the current group_members state attribute for an entity."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state.attributes.get(ATTR_GROUP_MEMBERS, [])


async def test_async_join_players(hass: HomeAssistant, create_player) -> None:
    """Media players are joined and atv is called with the correct output device ids."""
    entity_1, atv_1 = await create_player("player_1")
    entity_2, _ = await create_player("player_2")

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {ATTR_ENTITY_ID: entity_1, ATTR_GROUP_MEMBERS: [entity_1, entity_2]},
        blocking=True,
    )
    await hass.async_block_till_done()

    atv_1.audio.set_output_devices.assert_called_with(
        "player_1-output-device-id", "player_2-output-device-id"
    )
    assert _group_members(hass, entity_1) == [entity_1, entity_2]


async def test_async_join_players_throws(hass: HomeAssistant, create_player) -> None:
    """Joining raises on unknown entity ids, but still joins the valid entities."""
    entity_1, atv_1 = await create_player("player_1")
    entity_2, _ = await create_player("player_2")

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: entity_1,
                ATTR_GROUP_MEMBERS: [entity_1, entity_2, "media_player.does_not_exist"],
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    # The valid entities are still captured and joined.
    atv_1.audio.set_output_devices.assert_called_with(
        "player_1-output-device-id", "player_2-output-device-id"
    )
    assert _group_members(hass, entity_1) == [entity_1, entity_2]


async def test_async_unjoin_player(hass: HomeAssistant, create_player) -> None:
    """Leader players remove all members from their own group during unjoin."""
    entity_1, atv_1 = await create_player("player_1")
    entity_2, _ = await create_player("player_2")

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {ATTR_ENTITY_ID: entity_1, ATTR_GROUP_MEMBERS: [entity_1, entity_2]},
        blocking=True,
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {ATTR_ENTITY_ID: entity_1},
        blocking=True,
    )
    await hass.async_block_till_done()

    atv_1.audio.set_output_devices.assert_called_with("player_1-output-device-id")
    assert _group_members(hass, entity_1) == [entity_1]


async def test_async_unjoin_player_delegated(
    hass: HomeAssistant, create_player
) -> None:
    """Non-leader players are removed from another player's group during unjoin."""
    entity_1, atv_1 = await create_player("player_1")
    entity_2, _ = await create_player("player_2")

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {ATTR_ENTITY_ID: entity_1, ATTR_GROUP_MEMBERS: [entity_1, entity_2]},
        blocking=True,
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {ATTR_ENTITY_ID: entity_2},
        blocking=True,
    )

    atv_1.audio.remove_output_devices.assert_called_with("player_2-output-device-id")


async def test_outputdevices_update(hass: HomeAssistant, create_player) -> None:
    """When atv signals an outputdevices update, the group_members are updated."""
    entity_1, atv_1 = await create_player("player_1")
    entity_2, _ = await create_player("player_2")

    new_devices = [
        Mock(identifier="player_1-output-device-id"),
        Mock(identifier="player_2-output-device-id"),
        Mock(identifier="non-hass-player-output-device-id"),
    ]
    atv_1.audio.output_devices = new_devices
    atv_1.audio.listener.outputdevices_update([], new_devices)
    await hass.async_block_till_done()

    assert _group_members(hass, entity_1) == [entity_1, entity_2]


ENTITY_ID = "media_player.living_room_living_room"
_MUSIC_URL = "http://example.local:8123/api/tts_proxy/abc.mp3"
_VIDEO_URL = "http://example.local:8123/video.mp4"

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    ("play_item", "expected_stream_arg"),
    [
        (
            PlayMedia(
                url="/api/media_source_proxy/song.mp3",
                mime_type="audio/mp3",
                path=Path("/media/song.mp3"),
            ),
            "/media/song.mp3",
        ),
        (
            PlayMedia(
                url="https://example.com/song.mp3",
                mime_type="audio/mp3",
            ),
            "https://example.com/song.mp3",
        ),
    ],
)
async def test_play_media_from_media_source(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    play_item: PlayMedia,
    expected_stream_arg: str,
) -> None:
    """Stream resolved media via its local path when present, otherwise via the URL."""
    with patch(
        "homeassistant.components.apple_tv.media_player.media_source.async_resolve_media",
        return_value=play_item,
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://local/song.mp3",
            },
            blocking=True,
        )

    mock_atv.stream.stream_file.assert_awaited_once_with(expected_stream_arg)


@pytest.mark.parametrize("media_type", [MediaType.APP, MediaType.URL])
async def test_play_media_launches_app(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    media_type: MediaType,
) -> None:
    """App and URL media types launch the corresponding app on the device."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: "com.netflix.Netflix",
        },
        blocking=True,
    )

    mock_atv.apps.launch_app.assert_awaited_once_with("com.netflix.Netflix")
    mock_atv.stream.stream_file.assert_not_called()


@pytest.mark.parametrize(
    ("media_type", "media_id", "called_method", "stream_file_state"),
    [
        pytest.param(
            MediaType.MUSIC,
            _MUSIC_URL,
            "stream_file",
            FeatureState.Available,
            id="music_via_raop",
        ),
        pytest.param(
            MediaType.VIDEO,
            _VIDEO_URL,
            "play_url",
            FeatureState.Unsupported,
            id="video_via_airplay",
        ),
    ],
)
async def test_play_media_selects_streaming_method(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    media_type: MediaType,
    media_id: str,
    called_method: str,
    stream_file_state: FeatureState,
) -> None:
    """Streaming path is selected from device feature state, not _playing."""
    mock_atv.features.set_state(FeatureName.StreamFile, stream_file_state)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: media_id,
        },
        blocking=True,
    )

    getattr(mock_atv.stream, called_method).assert_awaited_once_with(media_id)


async def test_play_media_falls_back_to_play_url(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
) -> None:
    """When StreamFile is unavailable, play_url is used for video."""
    mock_atv.features.set_state(FeatureName.StreamFile, FeatureState.Unsupported)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.VIDEO,
            ATTR_MEDIA_CONTENT_ID: _VIDEO_URL,
        },
        blocking=True,
    )

    mock_atv.stream.play_url.assert_awaited_once_with(_VIDEO_URL)
    mock_atv.stream.stream_file.assert_not_called()


async def test_play_media_raises_when_no_streaming_method(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
) -> None:
    """Raise HomeAssistantError when no streaming method is available."""
    mock_atv.features.set_state(FeatureName.StreamFile, FeatureState.Unsupported)
    mock_atv.features.set_state(FeatureName.PlayUrl, FeatureState.Unsupported)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: _MUSIC_URL,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "streaming_not_supported"
    assert exc_info.value.translation_domain == DOMAIN
    mock_atv.stream.stream_file.assert_not_called()
    mock_atv.stream.play_url.assert_not_called()


@pytest.mark.parametrize(
    ("stream_attr", "media_type", "media_id", "stream_file_state"),
    [
        (
            "stream_file",
            MediaType.MUSIC,
            _MUSIC_URL,
            FeatureState.Available,
        ),
        (
            "play_url",
            MediaType.VIDEO,
            _VIDEO_URL,
            FeatureState.Unsupported,
        ),
    ],
)
@pytest.mark.parametrize(
    ("exc_class", "expected_translation_key"),
    [
        (BlockedStateError, "stream_failed"),
        (ConnectionLostError, "stream_failed"),
        (InvalidStateError, "stream_failed"),
        (NotSupportedError, "streaming_not_supported"),
        (OperationTimeoutError, "stream_failed"),
        (PlaybackError, "stream_failed"),
        (ProtocolError, "stream_failed"),
    ],
)
async def test_play_media_raises_ha_error_on_pyatv_failure(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    stream_attr: str,
    media_type: MediaType,
    media_id: str,
    stream_file_state: FeatureState,
    exc_class: type[Exception],
    expected_translation_key: str,
) -> None:
    """Pyatv streaming exceptions surface as a translated HomeAssistantError."""
    mock_atv.features.set_state(FeatureName.StreamFile, stream_file_state)
    getattr(mock_atv.stream, stream_attr).side_effect = exc_class("error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: media_type,
                ATTR_MEDIA_CONTENT_ID: media_id,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == expected_translation_key
    assert exc_info.value.translation_domain == DOMAIN


async def test_browse_media_uses_media_source(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """async_browse_media routes to media_source when streaming is available."""
    browse_result = BrowseMedia(
        title="Media",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="",
        can_play=False,
        can_expand=True,
        children=[],
    )

    with patch(
        "homeassistant.components.apple_tv.media_player.media_source.async_browse_media",
        new_callable=AsyncMock,
        return_value=browse_result,
    ) as mock_browse:
        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/browse_media",
                "entity_id": ENTITY_ID,
            }
        )
        response = await client.receive_json()

    assert response["success"]
    mock_browse.assert_called_once()
