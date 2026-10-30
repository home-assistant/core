"""Tests for the Apple TV media player."""

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

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
from pyatv.interface import OutputDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.apple_tv.const import DOMAIN
from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MP_DOMAIN,
    SERVICE_JOIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_UNJOIN,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.components.media_source import PlayMedia
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_NAME,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_VOLUME_SET,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import create_conf, mrp_service

ENTITY_ID = "media_player.living_room_living_room"
_MUSIC_URL = "http://example.local:8123/api/tts_proxy/abc.mp3"
_VIDEO_URL = "http://example.local:8123/video.mp4"
HOMEPOD_ENTITY_ID = "media_player.bedroom_bedroom"
ATV_OUTPUT_ID = "atv-output-id"
HOMEPOD_OUTPUT_ID = "homepod-output-id"
ATV_OUTPUT = OutputDevice(identifier=ATV_OUTPUT_ID, name="Living Room")
HOMEPOD_OUTPUT = OutputDevice(identifier=HOMEPOD_OUTPUT_ID, name="Bedroom")

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
            MP_DOMAIN,
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
        MP_DOMAIN,
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
        MP_DOMAIN,
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
        MP_DOMAIN,
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
            MP_DOMAIN,
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
            MP_DOMAIN,
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


@pytest.mark.parametrize(
    ("service", "service_data", "interface", "method"),
    [
        pytest.param(SERVICE_MEDIA_PAUSE, {}, "remote_control", "pause", id="pause"),
        pytest.param(
            SERVICE_MEDIA_NEXT_TRACK, {}, "remote_control", "next", id="next_track"
        ),
        pytest.param(
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            "audio",
            "set_volume",
            id="volume_set",
        ),
    ],
)
@pytest.mark.parametrize("exc_class", [TimeoutError, ConnectionLostError])
async def test_command_raises_ha_error_on_failure(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    service: str,
    service_data: dict[str, float],
    interface: str,
    method: str,
    exc_class: type[Exception],
) -> None:
    """Test a failing command surfaces as a translated HomeAssistantError."""
    getattr(getattr(mock_atv, interface), method).side_effect = exc_class("error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MP_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_failed"
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


HOMEPOD_SCAN_RESULT = create_conf(
    "127.0.0.2", "Bedroom", mrp_service(unique_id="homepodid")
)


def _homepod_device_patches(mock_homepod_atv: AsyncMock) -> ExitStack:
    """Patch pyatv so that the integration finds and connects to the HomePod."""
    stack = ExitStack()
    stack.enter_context(
        patch(
            "homeassistant.components.apple_tv.scan",
            return_value=[HOMEPOD_SCAN_RESULT],
        )
    )
    stack.enter_context(
        patch(
            "homeassistant.components.apple_tv.connect", return_value=mock_homepod_atv
        )
    )
    return stack


async def _setup_homepod(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    mock_homepod_atv: AsyncMock,
    atv_devices: list[OutputDevice],
    homepod_devices: list[OutputDevice],
) -> None:
    """Set up a HomePod next to the Apple TV, with the given output devices."""
    mock_atv.device_info.output_device_id = ATV_OUTPUT_ID
    mock_atv.audio.output_devices = atv_devices
    mock_homepod_atv.device_info.output_device_id = HOMEPOD_OUTPUT_ID
    mock_homepod_atv.audio.output_devices = homepod_devices
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bedroom",
        unique_id="homepodid",
        data={
            CONF_ADDRESS: "127.0.0.2",
            CONF_NAME: "Bedroom",
            "credentials": {str(Protocol.MRP.value): "mrp_creds"},
            "identifiers": ["homepodid"],
        },
    )
    entry.add_to_hass(hass)
    with _homepod_device_patches(mock_homepod_atv):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.fixture
async def mock_homepod(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_atv: AsyncMock,
    mock_homepod_atv: AsyncMock,
) -> AsyncMock:
    """Set up a HomePod next to the Apple TV, both playing alone."""
    await _setup_homepod(
        hass, mock_atv, mock_homepod_atv, [ATV_OUTPUT], [HOMEPOD_OUTPUT]
    )
    return mock_homepod_atv


async def _push_group(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    mock_homepod: AsyncMock,
    atv_devices: list[OutputDevice],
    homepod_devices: list[OutputDevice],
) -> None:
    """Change the output devices as the devices report them, then push the update."""
    mock_atv.audio.output_devices = atv_devices
    mock_homepod.audio.output_devices = homepod_devices
    mock_atv.audio.listener.outputdevices_update([], atv_devices)
    await hass.async_block_till_done()


@pytest.fixture
async def grouped(
    hass: HomeAssistant, mock_atv: AsyncMock, mock_homepod: AsyncMock
) -> None:
    """Group the HomePod under the Apple TV."""
    await _push_group(hass, mock_atv, mock_homepod, [ATV_OUTPUT, HOMEPOD_OUTPUT], [])


@pytest.mark.parametrize(
    ("atv_devices", "homepod_devices", "atv_members", "homepod_members"),
    [
        pytest.param(
            [ATV_OUTPUT],
            [HOMEPOD_OUTPUT],
            [ENTITY_ID],
            [HOMEPOD_ENTITY_ID],
            id="standalone",
        ),
        pytest.param(
            [ATV_OUTPUT, HOMEPOD_OUTPUT],
            [],
            [ENTITY_ID, HOMEPOD_ENTITY_ID],
            [ENTITY_ID, HOMEPOD_ENTITY_ID],
            id="grouped",
        ),
        pytest.param(
            [HOMEPOD_OUTPUT],
            [],
            [ENTITY_ID, HOMEPOD_ENTITY_ID],
            [ENTITY_ID, HOMEPOD_ENTITY_ID],
            id="leader_not_an_output",
        ),
    ],
)
async def test_group_members(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    mock_homepod: AsyncMock,
    atv_devices: list[OutputDevice],
    homepod_devices: list[OutputDevice],
    atv_members: list[str],
    homepod_members: list[str],
) -> None:
    """Both players report the group of the leader, leader first."""
    await _push_group(hass, mock_atv, mock_homepod, atv_devices, homepod_devices)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == atv_members
    assert (
        hass.states.get(HOMEPOD_ENTITY_ID).attributes[ATTR_GROUP_MEMBERS]
        == homepod_members
    )


async def test_group_members_without_output_devices(
    hass: HomeAssistant, mock_atv: AsyncMock, mock_homepod: AsyncMock
) -> None:
    """A player without the output devices feature is left out of grouping."""
    mock_homepod.features.set_state(FeatureName.OutputDevices, FeatureState.Unsupported)
    type(mock_homepod.audio).output_devices = PropertyMock(
        side_effect=NotSupportedError
    )

    mock_atv.audio.output_devices = [ATV_OUTPUT, HOMEPOD_OUTPUT]
    mock_atv.audio.listener.outputdevices_update([], mock_atv.audio.output_devices)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == [ENTITY_ID]
    assert hass.states.get(HOMEPOD_ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] is None


async def test_join(
    hass: HomeAssistant, mock_atv: AsyncMock, mock_homepod: AsyncMock
) -> None:
    """Joining adds the HomePod by its output device ID, and both players report it."""

    async def _add_output_devices(*devices: str) -> None:
        await _push_group(
            hass, mock_atv, mock_homepod, [ATV_OUTPUT, HOMEPOD_OUTPUT], []
        )

    mock_atv.audio.add_output_devices.side_effect = _add_output_devices

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_JOIN,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_GROUP_MEMBERS: [ENTITY_ID, HOMEPOD_ENTITY_ID]},
        blocking=True,
    )

    mock_atv.audio.add_output_devices.assert_awaited_once_with(HOMEPOD_OUTPUT_ID)
    expected = [ENTITY_ID, HOMEPOD_ENTITY_ID]
    assert hass.states.get(ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == expected
    assert hass.states.get(HOMEPOD_ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == expected


@pytest.mark.parametrize(
    "atv_devices",
    [
        pytest.param([ATV_OUTPUT], id="standalone"),
        pytest.param([HOMEPOD_OUTPUT], id="leader_not_an_output"),
    ],
)
async def test_join_only_self(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    mock_homepod: AsyncMock,
    atv_devices: list[OutputDevice],
) -> None:
    """Joining a player to itself sends nothing to the device."""
    await _push_group(hass, mock_atv, mock_homepod, atv_devices, [])

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_JOIN,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_GROUP_MEMBERS: [ENTITY_ID]},
        blocking=True,
    )

    mock_atv.audio.add_output_devices.assert_not_awaited()


@pytest.mark.parametrize(
    ("member", "translation_key"),
    [
        pytest.param(
            "media_player.kitchen", "invalid_grouping_entity", id="other_integration"
        ),
        pytest.param(
            "media_player.unknown", "invalid_grouping_entity", id="unknown_entity"
        ),
        pytest.param(
            "remote.living_room_living_room",
            "invalid_grouping_entity",
            id="apple_tv_remote",
        ),
        pytest.param(
            HOMEPOD_ENTITY_ID, "grouping_unavailable", id="no_output_device_id"
        ),
    ],
)
async def test_join_invalid_member(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_atv: AsyncMock,
    mock_homepod: AsyncMock,
    member: str,
    translation_key: str,
) -> None:
    """Joining a player that can't be grouped raises and changes nothing."""
    entity_registry.async_get_or_create(
        MP_DOMAIN, "demo", "kitchen", suggested_object_id="kitchen"
    )
    mock_homepod.device_info.output_device_id = None

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_JOIN,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_GROUP_MEMBERS: [member]},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    mock_atv.audio.add_output_devices.assert_not_awaited()


@pytest.mark.usefixtures("grouped")
async def test_join_already_grouped(hass: HomeAssistant, mock_atv: AsyncMock) -> None:
    """Joining a player that is already in the group sends nothing to the device."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_JOIN,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_GROUP_MEMBERS: [HOMEPOD_ENTITY_ID]},
        blocking=True,
    )

    mock_atv.audio.add_output_devices.assert_not_awaited()


@pytest.mark.usefixtures("mock_homepod")
async def test_join_device_error(hass: HomeAssistant, mock_atv: AsyncMock) -> None:
    """A pyatv error during join is raised as a command failure."""
    mock_atv.audio.add_output_devices.side_effect = ProtocolError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_JOIN,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_GROUP_MEMBERS: [HOMEPOD_ENTITY_ID]},
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_failed"


@pytest.mark.usefixtures("grouped")
@pytest.mark.parametrize(
    ("entity_id", "removed"),
    [
        pytest.param(ENTITY_ID, HOMEPOD_OUTPUT_ID, id="leader_ends_group"),
        pytest.param(HOMEPOD_ENTITY_ID, HOMEPOD_OUTPUT_ID, id="member_leaves"),
    ],
)
async def test_unjoin(
    hass: HomeAssistant, mock_atv: AsyncMock, entity_id: str, removed: str
) -> None:
    """Unjoin asks the leader to remove the member, from either player."""
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_UNJOIN, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    mock_atv.audio.remove_output_devices.assert_awaited_once_with(removed)


@pytest.mark.parametrize(
    ("atv_devices", "homepod_devices"),
    [
        pytest.param([ATV_OUTPUT], [HOMEPOD_OUTPUT], id="standalone"),
        pytest.param([ATV_OUTPUT], [], id="leader_not_in_home_assistant"),
    ],
)
async def test_unjoin_without_known_group(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    mock_homepod: AsyncMock,
    atv_devices: list[OutputDevice],
    homepod_devices: list[OutputDevice],
) -> None:
    """Unjoin sends nothing when Home Assistant knows no group for the player."""
    await _push_group(hass, mock_atv, mock_homepod, atv_devices, homepod_devices)

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_UNJOIN, {ATTR_ENTITY_ID: HOMEPOD_ENTITY_ID}, blocking=True
    )

    mock_atv.audio.remove_output_devices.assert_not_awaited()
    mock_homepod.audio.remove_output_devices.assert_not_awaited()


@pytest.mark.usefixtures("grouped")
async def test_group_members_drop_disabled_player(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """The leader stops listing a member whose entity is disabled."""
    entity_registry.async_update_entity(
        HOMEPOD_ENTITY_ID, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == [ENTITY_ID]


@pytest.mark.usefixtures("grouped")
async def test_group_members_follow_rename(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """The leader reports the new entity ID of a renamed member."""
    entity_registry.async_update_entity(
        HOMEPOD_ENTITY_ID, new_entity_id="media_player.bedroom_speaker"
    )
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == [
        ENTITY_ID,
        "media_player.bedroom_speaker",
    ]


@pytest.mark.usefixtures("grouped")
@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        pytest.param(
            SERVICE_JOIN, {ATTR_GROUP_MEMBERS: [HOMEPOD_ENTITY_ID]}, id="join"
        ),
        pytest.param(SERVICE_UNJOIN, {}, id="unjoin"),
    ],
)
async def test_leader_disconnected(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_atv: AsyncMock,
    service: str,
    service_data: dict[str, list[str]],
) -> None:
    """A disconnected leader has no group, and its member plays alone."""
    with patch("homeassistant.components.apple_tv.scan", return_value=[]):
        mock_atv.listener.connection_closed()
        await hass.async_block_till_done()

        assert hass.states.get(ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] is None
        assert hass.states.get(HOMEPOD_ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == [
            HOMEPOD_ENTITY_ID
        ]
        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                MP_DOMAIN,
                service,
                {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
                blocking=True,
            )
        assert exc_info.value.translation_key == "grouping_unavailable"

        await init_integration.runtime_data.disconnect()


async def test_group_members_at_setup(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_atv: AsyncMock,
    mock_homepod_atv: AsyncMock,
) -> None:
    """Players that are already grouped report the group when they are set up."""
    await _setup_homepod(
        hass, mock_atv, mock_homepod_atv, [ATV_OUTPUT, HOMEPOD_OUTPUT], []
    )

    expected = [ENTITY_ID, HOMEPOD_ENTITY_ID]
    assert hass.states.get(ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == expected
    assert hass.states.get(HOMEPOD_ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == expected


@pytest.mark.usefixtures("grouped")
async def test_member_reconnects(hass: HomeAssistant, mock_homepod: AsyncMock) -> None:
    """A member leaves the group while it is disconnected and is back after a reconnect."""
    expected = [ENTITY_ID, HOMEPOD_ENTITY_ID]
    with _homepod_device_patches(mock_homepod):
        mock_homepod.listener.connection_closed()
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == expected
    assert hass.states.get(HOMEPOD_ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == expected


@pytest.mark.usefixtures("grouped")
async def test_group_members_after_shutdown_disconnect(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_atv: AsyncMock,
    mock_homepod: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A closed connection that the entity still holds is not read for the group."""
    # pyatv blocks every call on a closed connection
    mock_atv.features = MagicMock(in_state=MagicMock(side_effect=BlockedStateError))
    type(mock_atv.audio).output_devices = PropertyMock(side_effect=BlockedStateError)

    await init_integration.runtime_data.disconnect()
    await hass.async_block_till_done()

    assert "Exception in _async_update_group_members" not in caplog.text
    assert hass.states.get(HOMEPOD_ENTITY_ID).attributes[ATTR_GROUP_MEMBERS] == [
        HOMEPOD_ENTITY_ID
    ]
