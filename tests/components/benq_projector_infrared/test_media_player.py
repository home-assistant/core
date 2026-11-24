"""Tests for the BenQ Projector Infrared media player platform."""

from infrared_protocols.codes.benq.projector import BenQProjectorCode
from infrared_protocols.commands.nec import NECCommand
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    MediaPlayerService,
    MediaPlayerServiceArgument,
    MediaPlayerState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TargetKey,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID, MOCK_INFRARED_RECEIVER_ENTITY_ID

MEDIA_PLAYER_ENTITY_ID = "media_player.benq_projector"


@pytest.mark.parametrize("has_receiver_entity", [False, True])
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the media player entity is created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "service_data", "expected_code"),
    [
        (SERVICE_TURN_ON, {}, BenQProjectorCode.POWER_ON),
        (SERVICE_TURN_OFF, {}, BenQProjectorCode.POWER_OFF),
        (SERVICE_VOLUME_UP, {}, BenQProjectorCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, {}, BenQProjectorCode.VOLUME_DOWN),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, BenQProjectorCode.MUTE),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": False}, BenQProjectorCode.MUTE),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    service_data: dict[str, bool],
    expected_code: BenQProjectorCode,
) -> None:
    """Test each media player action sends the correct IR code."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, **service_data},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        ("hdmi_1", BenQProjectorCode.HDMI_1),
        ("hdmi_2", BenQProjectorCode.HDMI_2),
        ("pc_1", BenQProjectorCode.PC_1),
        ("component_1", BenQProjectorCode.COMPONENT_1),
        ("video_1", BenQProjectorCode.VIDEO_1),
        ("s_video_1", BenQProjectorCode.S_VIDEO_1),
        ("dvi_d", BenQProjectorCode.DVI_D),
        ("usb_reader", BenQProjectorCode.USB_READER),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_select_source(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    source: str,
    expected_code: BenQProjectorCode,
) -> None:
    """Test selecting a source sends the correct IR code and updates state."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.SELECT_SOURCE,
        {
            TargetKey.ENTITY_ID: MEDIA_PLAYER_ENTITY_ID,
            MediaPlayerServiceArgument.SOURCE: source,
        },
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == source
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == [
        "hdmi_1",
        "hdmi_2",
        "pc_1",
        "pc_2",
        "component_1",
        "component_2",
        "video_1",
        "video_2",
        "s_video_1",
        "s_video_2",
        "dvi_d",
        "usb_reader",
    ]


@pytest.mark.usefixtures("init_integration")
async def test_select_invalid_source(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Selecting an unknown source raises a validation error and sends nothing."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            MediaPlayerService.SELECT_SOURCE,
            {
                TargetKey.ENTITY_ID: MEDIA_PLAYER_ENTITY_ID,
                MediaPlayerServiceArgument.SOURCE: "hdmi_3",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_source"
    assert exc_info.value.translation_placeholders == {
        "invalid_source": "hdmi_3",
        "valid_sources": (
            "hdmi_1, hdmi_2, pc_1, pc_2, component_1, component_2, video_1, "
            "video_2, s_video_1, s_video_2, dvi_d, usb_reader"
        ),
    }
    assert mock_infrared_emitter_entity.send_command_calls == []


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_off_update_assumed_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Turn-off and turn-on update the assumed state."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.TURN_OFF,
        {TargetKey.ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.OFF

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.TURN_ON,
        {TargetKey.ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.ON

    assert mock_infrared_emitter_entity.send_command_calls == [
        BenQProjectorCode.POWER_OFF,
        BenQProjectorCode.POWER_ON,
    ]


@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test media player becomes unavailable when IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, MEDIA_PLAYER_ENTITY_ID, [MOCK_INFRARED_EMITTER_ENTITY_ID]
    )


@pytest.mark.usefixtures("init_integration")
async def test_initial_state_unknown_when_no_restore(hass: HomeAssistant) -> None:
    """With no previous state to restore, the entity reports unknown."""
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_INPUT_SOURCE) is None


@pytest.mark.parametrize(
    "restored_state",
    [MediaPlayerState.ON, MediaPlayerState.OFF],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_benq_to_command")
async def test_restores_state_and_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    restored_state: MediaPlayerState,
) -> None:
    """State and source survive a restart, even when OFF."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(MEDIA_PLAYER_ENTITY_ID, restored_state),
                {"power_state": restored_state, "source": "hdmi_2"},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == restored_state

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.TURN_ON,
        {TargetKey.ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == "hdmi_2"


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_benq_to_command")
async def test_restores_power_state_after_emitter_outage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The power state survives a restart while the emitter was unavailable."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(MEDIA_PLAYER_ENTITY_ID, STATE_UNAVAILABLE),
                {"power_state": MediaPlayerState.ON, "source": None},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.ON


async def test_turn_on_sends_benq_nec_frame(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Turning on sends a real extended NEC frame on BenQ's custom code 0x30.

    The expected frame is built explicitly, so a wrong address or byte order in
    the codes is caught as well.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.TURN_ON,
        {TargetKey.ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == NECCommand(address=0x3000, command=0x4F).get_raw_timings()


def _receive(
    receiver: MockInfraredReceiverEntity, command: int, address: int = 0x3000
) -> None:
    """Feed a NEC frame from the physical remote into the receiver."""
    receiver._handle_received_signal(
        InfraredReceivedSignal(
            timings=NECCommand(address=address, command=command).get_raw_timings()
        )
    )


@pytest.mark.parametrize(
    ("initial_state", "command", "expected_state"),
    [
        (MediaPlayerState.OFF, 0x4F, MediaPlayerState.ON),
        (MediaPlayerState.ON, 0x4E, MediaPlayerState.OFF),
        (MediaPlayerState.ON, 0x02, MediaPlayerState.OFF),
        (MediaPlayerState.OFF, 0x02, MediaPlayerState.ON),
    ],
)
@pytest.mark.parametrize("has_receiver_entity", [True])
@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_benq_to_command")
async def test_receiver_power_codes_update_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    initial_state: MediaPlayerState,
    command: int,
    expected_state: MediaPlayerState,
) -> None:
    """Power codes from the physical remote update the assumed power state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(MEDIA_PLAYER_ENTITY_ID, initial_state),
                {"power_state": initial_state, "source": None},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    _receive(mock_infrared_receiver_entity, command)
    await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize("has_receiver_entity", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_power_toggle_ignored_when_state_unknown(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """The power toggle cannot be followed when the power state is unknown."""
    _receive(mock_infrared_receiver_entity, 0x02)
    await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("has_receiver_entity", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_source_codes_update_source(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Input keys set the source, and the cycling source key clears it."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.TURN_ON,
        {TargetKey.ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    _receive(mock_infrared_receiver_entity, 0x59)
    await hass.async_block_till_done()
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == "hdmi_2"

    _receive(mock_infrared_receiver_entity, 0x04)
    await hass.async_block_till_done()
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert ATTR_INPUT_SOURCE not in state.attributes

    # Receiving only updates the state; nothing is sent back.
    assert mock_infrared_emitter_entity.send_command_calls == [
        BenQProjectorCode.POWER_ON
    ]


@pytest.mark.parametrize(
    "timings",
    [
        pytest.param(
            NECCommand(address=0x7C87, command=0x4F).get_raw_timings(),
            id="other_address",
        ),
        pytest.param(
            NECCommand(address=0x3000, command=0x01).get_raw_timings(),
            id="unknown_command",
        ),
        pytest.param(
            NECCommand(address=0x3000, command=0x82).get_raw_timings(),
            id="untracked_command",
        ),
        pytest.param([1, 2, 3, 4], id="not_nec"),
    ],
)
@pytest.mark.parametrize("has_receiver_entity", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_other_signals(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    timings: list[int],
) -> None:
    """Signals that are not BenQ power or source codes leave the state alone."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=timings)
    )
    await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_INPUT_SOURCE) is None


@pytest.mark.parametrize("has_receiver_entity", [True])
@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_receiver(
    hass: HomeAssistant,
) -> None:
    """With a receiver configured, the media player also follows its availability."""
    await assert_availability_follows_source_entity(
        hass,
        MEDIA_PLAYER_ENTITY_ID,
        [MOCK_INFRARED_EMITTER_ENTITY_ID, MOCK_INFRARED_RECEIVER_ENTITY_ID],
    )
