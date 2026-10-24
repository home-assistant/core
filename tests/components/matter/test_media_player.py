"""Test Matter media players."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from chip.clusters.ClusterObjects import ClusterCommand
from freezegun.api import FrozenDateTimeFactory
from matter_server.client.models.node import MatterNode
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.matter.media_player import STATE_WRITE_DEBOUNCE_COOLDOWN
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_SEEK_POSITION,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

ENTITY_ID = "media_player.mock_basic_video_player"

ALL_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.SELECT_SOURCE
)


@pytest.fixture(name="attributes")
def attributes_fixture(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Override node attributes for a parametrized test."""
    return getattr(request, "param", {})


async def trigger_subscription_callback_debounced(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
) -> None:
    """Trigger subscription callbacks and wait for the debounced state write."""
    await trigger_subscription_callback(hass, client)
    freezer.tick(STATE_WRITE_DEBOUNCE_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("matter_devices")
async def test_media_players(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test media players."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.MEDIA_PLAYER)


@pytest.mark.parametrize("node_fixture", ["mock_basic_video_player"])
@pytest.mark.parametrize(
    ("attributes", "expected_state"),
    [
        pytest.param({"1/6/0": False}, MediaPlayerState.OFF, id="off"),
        pytest.param({"1/1286/0": 0}, MediaPlayerState.PLAYING, id="playing"),
        pytest.param({"1/1286/0": 1}, MediaPlayerState.PAUSED, id="paused"),
        pytest.param({"1/1286/0": 2}, MediaPlayerState.IDLE, id="not_playing"),
        pytest.param({"1/1286/0": 3}, MediaPlayerState.BUFFERING, id="buffering"),
    ],
    indirect=["attributes"],
)
@pytest.mark.usefixtures("matter_node")
async def test_state(
    hass: HomeAssistant,
    expected_state: MediaPlayerState,
) -> None:
    """Test the state follows On/Off and the Media Playback CurrentState."""
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == expected_state


@pytest.mark.parametrize("node_fixture", ["mock_basic_video_player"])
@pytest.mark.parametrize(
    ("attributes", "expected_features"),
    [
        pytest.param({}, ALL_FEATURES, id="all"),
        pytest.param(
            {"1/6/65532": clusters.OnOff.Bitmaps.Feature.kOffOnly},
            ALL_FEATURES & ~MediaPlayerEntityFeature.TURN_ON,
            id="off_only",
        ),
        pytest.param(
            {"1/1286/65529": [0, 1, 2]},
            ALL_FEATURES
            & ~MediaPlayerEntityFeature.PREVIOUS_TRACK
            & ~MediaPlayerEntityFeature.NEXT_TRACK
            & ~MediaPlayerEntityFeature.SEEK,
            id="mandatory_playback_commands_only",
        ),
        pytest.param(
            {"1/1287/0": []},
            ALL_FEATURES & ~MediaPlayerEntityFeature.SELECT_SOURCE,
            id="no_inputs",
        ),
    ],
    indirect=["attributes"],
)
@pytest.mark.usefixtures("matter_node")
async def test_supported_features(
    hass: HomeAssistant,
    expected_features: MediaPlayerEntityFeature,
) -> None:
    """Test the supported features follow the device's capabilities."""
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == expected_features


@pytest.mark.parametrize("node_fixture", ["mock_basic_video_player"])
async def test_supported_features_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the supported features follow capability changes at runtime."""
    set_node_attribute(matter_node, 1, 1286, 65529, [0, 1, 2, 5])
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        ALL_FEATURES
        & ~MediaPlayerEntityFeature.PREVIOUS_TRACK
        & ~MediaPlayerEntityFeature.SEEK
    )

    set_node_attribute(matter_node, 1, 1287, 0, [])
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        ALL_FEATURES
        & ~MediaPlayerEntityFeature.PREVIOUS_TRACK
        & ~MediaPlayerEntityFeature.SEEK
        & ~MediaPlayerEntityFeature.SELECT_SOURCE
    )


@pytest.mark.parametrize("node_fixture", ["mock_basic_video_player"])
@pytest.mark.parametrize(
    ("service", "service_data", "command"),
    [
        (SERVICE_TURN_ON, {}, clusters.OnOff.Commands.On()),
        (SERVICE_TURN_OFF, {}, clusters.OnOff.Commands.Off()),
        (SERVICE_MEDIA_PLAY, {}, clusters.MediaPlayback.Commands.Play()),
        (SERVICE_MEDIA_PAUSE, {}, clusters.MediaPlayback.Commands.Pause()),
        (SERVICE_MEDIA_STOP, {}, clusters.MediaPlayback.Commands.Stop()),
        (
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {},
            clusters.MediaPlayback.Commands.Previous(),
        ),
        (SERVICE_MEDIA_NEXT_TRACK, {}, clusters.MediaPlayback.Commands.Next()),
        (
            SERVICE_MEDIA_SEEK,
            {ATTR_MEDIA_SEEK_POSITION: 90.5},
            clusters.MediaPlayback.Commands.Seek(position=90500),
        ),
        (
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "HDMI 2"},
            clusters.MediaInput.Commands.SelectInput(index=2),
        ),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    service: str,
    service_data: dict[str, Any],
    command: ClusterCommand,
) -> None:
    """Test media player actions send the matching Matter command."""
    matter_client.send_device_command.return_value = {"status": 0}
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args_list == [
        call(node_id=matter_node.node_id, endpoint_id=1, command=command)
    ]


@pytest.mark.parametrize("node_fixture", ["mock_basic_video_player"])
@pytest.mark.parametrize(
    ("response", "translation_key", "placeholders"),
    [
        (
            {"status": 1, "data": "Nothing is playing"},
            "media_playback_invalid_state",
            None,
        ),
        ({"status": 2}, "media_playback_not_allowed", None),
        ({"status": 3}, "media_playback_not_active", None),
        ({"status": 4}, "media_playback_speed_out_of_range", None),
        ({"status": 5}, "media_playback_seek_out_of_range", None),
        ({"status": 42}, "media_playback_failed", {"status": "42"}),
    ],
)
@pytest.mark.usefixtures("matter_node")
async def test_playback_command_rejected(
    hass: HomeAssistant,
    matter_client: MagicMock,
    response: dict[str, Any],
    translation_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Test a non-success PlaybackResponse raises the error for its status."""
    matter_client.send_device_command.return_value = response
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == placeholders


@pytest.mark.parametrize("node_fixture", ["mock_basic_video_player"])
@pytest.mark.usefixtures("matter_node")
async def test_select_unknown_source(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test selecting an input the device does not have."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "SCART"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "unknown_media_input"
    assert matter_client.send_device_command.call_count == 0


@pytest.mark.parametrize("node_fixture", ["mock_basic_video_player"])
async def test_position(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the playback position, converted from the Matter epoch."""
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_MEDIA_DURATION] == 7200
    assert state.attributes[ATTR_MEDIA_POSITION] == 0
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] == datetime(
        2026, 10, 13, 13, 0, 8, 656000, tzinfo=UTC
    )

    set_node_attribute(matter_node, 1, 1286, 3, {"0": 845212000000000, "1": 95250})
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_MEDIA_POSITION] == 95.25
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] == datetime(
        2026, 10, 13, 13, 6, 40, tzinfo=UTC
    )

    # The Matter SDK example TV app always reports 0 for updatedAt
    set_node_attribute(matter_node, 1, 1286, 3, {"0": 0, "1": 95250})
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert ATTR_MEDIA_POSITION not in state.attributes
    assert ATTR_MEDIA_POSITION_UPDATED_AT not in state.attributes

    set_node_attribute(matter_node, 1, 1286, 3, {"0": 845212000000000, "1": None})
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert ATTR_MEDIA_POSITION not in state.attributes


@pytest.mark.parametrize("node_fixture", ["mock_basic_video_player"])
async def test_sources(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the input list and the current input."""
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == [
        "Live TV",
        "HDMI 1",
        "HDMI 2",
        "HDMI 3",
        "USB",
    ]
    assert state.attributes[ATTR_INPUT_SOURCE] == "Live TV"

    set_node_attribute(matter_node, 1, 1287, 1, 3)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_INPUT_SOURCE] == "HDMI 3"


@pytest.mark.parametrize("node_fixture", ["mock_basic_video_player"])
@pytest.mark.parametrize(
    ("attributes", "source_list", "selected", "index"),
    [
        pytest.param(
            {
                "1/1287/0": [
                    {"0": 1, "1": 4, "2": "Console", "3": ""},
                    {"0": 2, "1": 4, "2": "Console", "3": ""},
                    {"0": 4, "1": 10, "2": "USB", "3": ""},
                ],
                "1/1287/1": 2,
            },
            ["Console (1)", "Console (2)", "USB"],
            "Console (1)",
            1,
            id="duplicate_names",
        ),
        pytest.param(
            {
                "1/1287/0": [
                    {"0": 1, "1": 4, "2": "Console", "3": ""},
                    {"0": 2, "1": 4, "2": "Console", "3": ""},
                    {"0": 4, "1": 4, "2": "Console (1)", "3": ""},
                ],
                "1/1287/1": 2,
            },
            ["Console (1)", "Console (2)", "Console (1) (4)"],
            "Console (1) (4)",
            4,
            id="name_like_generated_name",
        ),
    ],
)
async def test_duplicate_source_names(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    source_list: list[str],
    selected: str,
    index: int,
) -> None:
    """Test inputs with the same name are told apart by their index."""
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == source_list
    assert state.attributes[ATTR_INPUT_SOURCE] == "Console (2)"

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: selected},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args_list == [
        call(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.MediaInput.Commands.SelectInput(index=index),
        )
    ]
