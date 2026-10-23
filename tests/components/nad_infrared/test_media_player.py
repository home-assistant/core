"""Tests for the NAD Infrared media player platform."""

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
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    MediaPlayerState,
)
from homeassistant.components.nad_infrared.codes import (
    NADAmplifierCode,
    NADCassetteCode,
    NADCDCode,
)
from homeassistant.components.nad_infrared.const import NADDeviceType
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

MEDIA_PLAYER_ENTITY_ID = "media_player.nad_receiver"
CD_PLAYER_ENTITY_ID = "media_player.nad_cd_player"
CASSETTE_DECK_ENTITY_ID = "media_player.nad_cassette_deck"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.MEDIA_PLAYER]


@pytest.mark.parametrize(
    "device_type",
    list(NADDeviceType),
    indirect=True,
)
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
        (SERVICE_TURN_ON, {}, NADAmplifierCode.ON),
        (SERVICE_TURN_OFF, {}, NADAmplifierCode.OFF),
        (SERVICE_VOLUME_UP, {}, NADAmplifierCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, {}, NADAmplifierCode.VOLUME_DOWN),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, NADAmplifierCode.MUTE),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": False}, NADAmplifierCode.MUTE),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    service_data: dict[str, bool],
    expected_code: NADAmplifierCode,
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
        ("input_1", NADAmplifierCode.INPUT_1),
        ("input_4", NADAmplifierCode.INPUT_4),
        ("input_7", NADAmplifierCode.INPUT_7),
        ("front", NADAmplifierCode.FRONT),
        ("mp", NADAmplifierCode.MP),
        ("tuner", NADAmplifierCode.TUNER),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_select_source(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    source: str,
    expected_code: NADAmplifierCode,
) -> None:
    """Test selecting a source sends the correct IR code and updates state."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_INPUT_SOURCE: source},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == source
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == [
        "input_1",
        "input_2",
        "input_3",
        "input_4",
        "input_5",
        "input_6",
        "input_7",
        "front",
        "mp",
        "tuner",
    ]


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_off_update_assumed_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Turn-off and turn-on update the assumed state."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.OFF

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.ON

    assert mock_infrared_emitter_entity.send_command_calls == [
        NADAmplifierCode.OFF,
        NADAmplifierCode.ON,
    ]


@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test media player becomes unavailable when IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, MEDIA_PLAYER_ENTITY_ID, [MOCK_INFRARED_EMITTER_ENTITY_ID]
    )


@pytest.mark.parametrize(
    "restored_state",
    [MediaPlayerState.ON, MediaPlayerState.OFF],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_nad_to_command")
async def test_restores_state_source_and_sound_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    restored_state: MediaPlayerState,
) -> None:
    """State, source and sound mode survive a restart, even when OFF."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(MEDIA_PLAYER_ENTITY_ID, restored_state),
                {
                    "power_state": restored_state,
                    "source": "input_3",
                    "sound_mode": "neo6_cinema",
                },
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
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == "input_3"
    assert state.attributes[ATTR_SOUND_MODE] == "neo6_cinema"


@pytest.mark.usefixtures("init_integration")
async def test_initial_state_unknown_when_no_restore(hass: HomeAssistant) -> None:
    """With no previous state to restore, the entity reports unknown."""
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_INPUT_SOURCE) is None


@pytest.mark.parametrize("device_type", [NADDeviceType.AMPLIFIER], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_amplifier_media_player_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """The amplifier media player sends the same codes as the receiver."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "media_player.nad_amplifier"},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [NADAmplifierCode.ON]


@pytest.mark.usefixtures("init_integration")
async def test_select_invalid_source(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Selecting an unknown source raises a validation error and sends nothing."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_INPUT_SOURCE: "input_8"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_source"
    assert exc_info.value.translation_placeholders == {
        "invalid_source": "input_8",
        "valid_sources": (
            "input_1, input_2, input_3, input_4, input_5, input_6, input_7, "
            "front, mp, tuner"
        ),
    }
    assert mock_infrared_emitter_entity.send_command_calls == []


@pytest.mark.parametrize(
    ("sound_mode", "expected_code"),
    [
        ("pliix_movie", NADAmplifierCode.PLIIX_MOVIE),
        ("pliix_music", NADAmplifierCode.PLIIX_MUSIC),
        ("dolby_surround_ex", NADAmplifierCode.DOLBY_SURROUND_EX),
        ("neo6_cinema", NADAmplifierCode.NEO6_CINEMA),
        ("neo6_music", NADAmplifierCode.NEO6_MUSIC),
        ("ears", NADAmplifierCode.EARS),
        ("enhanced_stereo", NADAmplifierCode.ENHANCED_STEREO_1),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_sound_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    sound_mode: str,
    expected_code: NADAmplifierCode,
) -> None:
    """Selecting a sound mode sends its code and updates the assumed state."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_SOUND_MODE: sound_mode},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_SOUND_MODE] == sound_mode
    assert state.attributes[ATTR_SOUND_MODE_LIST] == [
        "pliix_movie",
        "pliix_music",
        "dolby_surround_ex",
        "neo6_cinema",
        "neo6_music",
        "matrix_7_1",
        "ears",
        "enhanced_stereo",
        "stereo_downmix",
        "direct",
        "bypass",
    ]


@pytest.mark.usefixtures("init_integration")
async def test_select_invalid_sound_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Selecting an unknown sound mode raises a validation error and sends nothing."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOUND_MODE,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_SOUND_MODE: "dolby_atmos"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_sound_mode"
    assert exc_info.value.translation_placeholders["invalid_sound_mode"] == (
        "dolby_atmos"
    )
    assert mock_infrared_emitter_entity.send_command_calls == []


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_nad_to_command")
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
                {
                    "power_state": MediaPlayerState.ON,
                    "source": None,
                    "sound_mode": None,
                },
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.ON


async def test_turn_on_sends_nad_nec_frame(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Turning on sends a real NEC frame on NAD's 877C address.

    The expected frame is built explicitly, so a wrong address or byte order in
    the codes is caught as well.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == NECCommand(address=0x7C87, command=0x25).get_raw_timings()


@pytest.mark.parametrize(
    ("service", "expected_code", "expected_state"),
    [
        (SERVICE_MEDIA_PLAY, NADCDCode.PLAY, MediaPlayerState.PLAYING),
        (SERVICE_MEDIA_PAUSE, NADCDCode.PAUSE, MediaPlayerState.PAUSED),
        (SERVICE_MEDIA_STOP, NADCDCode.STOP, MediaPlayerState.IDLE),
        (SERVICE_MEDIA_NEXT_TRACK, NADCDCode.SKIP_FORWARD, STATE_UNKNOWN),
        (SERVICE_MEDIA_PREVIOUS_TRACK, NADCDCode.SKIP_BACK, STATE_UNKNOWN),
    ],
)
@pytest.mark.parametrize("device_type", [NADDeviceType.CD_PLAYER], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_cd_player_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    expected_code: NADCDCode,
    expected_state: str,
) -> None:
    """Test each CD player action sends the correct IR code and sets the state."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: CD_PLAYER_ENTITY_ID},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]
    state = hass.states.get(CD_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_code", "expected_state"),
    [
        (SERVICE_MEDIA_PLAY, NADCassetteCode.DECK_B_PLAY, MediaPlayerState.PLAYING),
        (SERVICE_MEDIA_PAUSE, NADCassetteCode.DECK_B_PAUSE, MediaPlayerState.PAUSED),
        (SERVICE_MEDIA_STOP, NADCassetteCode.DECK_B_STOP, MediaPlayerState.IDLE),
    ],
)
@pytest.mark.parametrize("device_type", [NADDeviceType.CASSETTE_DECK], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_cassette_deck_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    expected_code: NADCassetteCode,
    expected_state: str,
) -> None:
    """Test each cassette deck action sends the correct IR code and sets the state."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: CASSETTE_DECK_ENTITY_ID},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]
    state = hass.states.get(CASSETTE_DECK_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
