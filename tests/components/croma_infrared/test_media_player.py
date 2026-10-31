"""Tests for the Croma Infrared media player platform."""

from unittest.mock import patch

from infrared_protocols.codes.croma.tv import CromaTVCode
from infrared_protocols.commands.nec import NECCommand
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    mock_restore_cache,
    snapshot_platform,
)
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

MEDIA_PLAYER_ENTITY_ID = "media_player.croma_tv"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.MEDIA_PLAYER]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the media player entity is created with the correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        ("croma_infrared", mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("service", "expected_code", "expected_state"),
    [
        (SERVICE_TURN_ON, CromaTVCode.POWER, MediaPlayerState.ON),
        (SERVICE_TURN_OFF, CromaTVCode.POWER, MediaPlayerState.OFF),
        (SERVICE_MEDIA_PLAY, CromaTVCode.PLAY, MediaPlayerState.PLAYING),
        (SERVICE_MEDIA_PAUSE, CromaTVCode.PAUSE, MediaPlayerState.PAUSED),
        (SERVICE_MEDIA_STOP, CromaTVCode.STOP, MediaPlayerState.ON),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_state_changing_commands(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    expected_code: CromaTVCode,
    expected_state: MediaPlayerState,
) -> None:
    """Test commands that send a code and update the assumed state."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_code"),
    [
        (SERVICE_VOLUME_UP, CromaTVCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, CromaTVCode.VOLUME_DOWN),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_stateless_commands(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    expected_code: CromaTVCode,
) -> None:
    """Test commands that only send a code."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]


@pytest.mark.parametrize("mute", [True, False])
@pytest.mark.usefixtures("init_integration")
async def test_mute(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mute: bool,
) -> None:
    """Test muting sends the mute toggle and tracks the requested state."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: mute},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [CromaTVCode.MUTE]
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is mute


@pytest.mark.parametrize("mute", [True, False])
@pytest.mark.usefixtures("init_integration")
async def test_repeated_mute_sends_each_time(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mute: bool,
) -> None:
    """Test every mute request sends the toggle, even if the state matches."""
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_MUTE,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: mute},
            blocking=True,
        )

    assert mock_infrared_emitter_entity.send_command_calls == [
        CromaTVCode.MUTE,
        CromaTVCode.MUTE,
    ]
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is mute


@pytest.mark.parametrize(
    ("service", "restored_state", "expected_state"),
    [
        (SERVICE_TURN_ON, MediaPlayerState.ON, MediaPlayerState.ON),
        (SERVICE_TURN_ON, MediaPlayerState.PLAYING, MediaPlayerState.ON),
        (SERVICE_TURN_ON, MediaPlayerState.PAUSED, MediaPlayerState.ON),
        (SERVICE_TURN_OFF, MediaPlayerState.OFF, MediaPlayerState.OFF),
    ],
)
@pytest.mark.usefixtures("mock_croma_to_command")
async def test_power_sent_when_already_in_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    service: str,
    restored_state: MediaPlayerState,
    expected_state: MediaPlayerState,
) -> None:
    """Test power is sent even when the assumed state already matches.

    The state is only assumed, so this is how a TV that is out of step with
    Home Assistant gets brought back in line.
    """
    mock_restore_cache(hass, [State(MEDIA_PLAYER_ENTITY_ID, restored_state)])

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.croma_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [CromaTVCode.POWER]
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_code"),
    [
        (SERVICE_MEDIA_PLAY, CromaTVCode.PLAY),
        (SERVICE_MEDIA_PAUSE, CromaTVCode.PAUSE),
        (SERVICE_MEDIA_STOP, CromaTVCode.STOP),
    ],
)
@pytest.mark.usefixtures("mock_croma_to_command")
async def test_playback_keeps_off_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    service: str,
    expected_code: CromaTVCode,
) -> None:
    """Test playback while off sends the code but keeps the off state."""
    mock_restore_cache(hass, [State(MEDIA_PLAYER_ENTITY_ID, MediaPlayerState.OFF)])

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.croma_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.state == MediaPlayerState.OFF


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        ("youtube", CromaTVCode.YOUTUBE),
        ("netflix", CromaTVCode.NETFLIX),
        ("prime_video", CromaTVCode.PRIME_VIDEO),
        ("live_tv", CromaTVCode.LIVE_TV),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_source(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    source: str,
    expected_code: CromaTVCode,
) -> None:
    """Test selecting a source opens its app and tracks the source."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_INPUT_SOURCE: source},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_INPUT_SOURCE] == source


@pytest.mark.usefixtures("init_integration")
async def test_select_invalid_source(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test selecting an unknown source raises and sends nothing."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_INPUT_SOURCE: "hdmi_1"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_source"
    assert mock_infrared_emitter_entity.send_command_calls == []


async def test_sends_nec_frame(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
) -> None:
    """Test commands go out as NEC frames on the Croma address."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.croma_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    [command] = mock_infrared_emitter_entity.send_command_calls
    assert isinstance(command, NECCommand)
    assert command.address == 0xBF40
    assert command.command == 0x12


@pytest.mark.usefixtures("init_integration")
async def test_state_unknown_without_restored_state(hass: HomeAssistant) -> None:
    """Test the entity starts as unknown when nothing was restored."""
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "restored_state",
    [
        MediaPlayerState.ON,
        MediaPlayerState.OFF,
        MediaPlayerState.PLAYING,
        MediaPlayerState.PAUSED,
    ],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_restore_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
    restored_state: MediaPlayerState,
) -> None:
    """Test the assumed state is restored across restarts."""
    mock_restore_cache(hass, [State(MEDIA_PLAYER_ENTITY_ID, restored_state)])

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.croma_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.state == restored_state


@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test the media player becomes unavailable when the IR entity is."""
    await assert_availability_follows_source_entity(
        hass, MEDIA_PLAYER_ENTITY_ID, [MOCK_INFRARED_EMITTER_ENTITY_ID]
    )
