"""Tests for the Persang Infrared media player platform."""

from unittest.mock import patch

from infrared_protocols.codes.persang.speaker import PersangSpeakerCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

from tests.common import (
    MockConfigEntry,
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared.common import MockInfraredEmitterEntity

MEDIA_PLAYER_ENTITY_ID = "media_player.persang_speaker"


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
        ("persang_infrared", mock_config_entry.entry_id), mock_config_entry.entry_id
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
        (SERVICE_TURN_ON, PersangSpeakerCode.POWER, MediaPlayerState.ON),
        (SERVICE_TURN_OFF, PersangSpeakerCode.POWER, MediaPlayerState.OFF),
        (SERVICE_MEDIA_PLAY, PersangSpeakerCode.PLAY_PAUSE, MediaPlayerState.PLAYING),
        (SERVICE_MEDIA_PAUSE, PersangSpeakerCode.PLAY_PAUSE, MediaPlayerState.PAUSED),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_state_changing_commands(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    expected_code: PersangSpeakerCode,
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
        (SERVICE_VOLUME_UP, PersangSpeakerCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, PersangSpeakerCode.VOLUME_DOWN),
        (SERVICE_MEDIA_NEXT_TRACK, PersangSpeakerCode.NEXT),
        (SERVICE_MEDIA_PREVIOUS_TRACK, PersangSpeakerCode.PREVIOUS),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_stateless_commands(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    expected_code: PersangSpeakerCode,
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

    assert mock_infrared_emitter_entity.send_command_calls == [PersangSpeakerCode.MUTE]
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is mute


@pytest.mark.parametrize(
    ("restored_state", "service"),
    [
        (MediaPlayerState.ON, SERVICE_TURN_ON),
        (MediaPlayerState.PLAYING, SERVICE_TURN_ON),
        (MediaPlayerState.PAUSED, SERVICE_TURN_ON),
        (MediaPlayerState.OFF, SERVICE_TURN_OFF),
        (MediaPlayerState.PLAYING, SERVICE_MEDIA_PLAY),
        (MediaPlayerState.PAUSED, SERVICE_MEDIA_PAUSE),
    ],
)
async def test_toggle_skipped_when_state_already_matches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    restored_state: MediaPlayerState,
    service: str,
) -> None:
    """Test a toggle is not sent when the speaker already is in the target state."""
    mock_restore_cache(hass, [State(MEDIA_PLAYER_ENTITY_ID, restored_state)])

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.persang_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    assert not mock_infrared_emitter_entity.send_command_calls
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.state == restored_state


@pytest.mark.parametrize("mute", [True, False])
async def test_mute_skipped_when_already_at_requested_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    mute: bool,
) -> None:
    """Test the mute toggle is not sent when mute already is at the wanted value."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(MEDIA_PLAYER_ENTITY_ID, MediaPlayerState.ON),
                {"is_volume_muted": mute},
            )
        ],
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.persang_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: mute},
        blocking=True,
    )

    assert not mock_infrared_emitter_entity.send_command_calls
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is mute


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
    with patch("homeassistant.components.persang_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.state == restored_state


@pytest.mark.parametrize("restored_mute", [True, False])
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_restore_mute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
    restored_mute: bool,
) -> None:
    """Test mute is restored even from the OFF state, which strips it."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(MEDIA_PLAYER_ENTITY_ID, MediaPlayerState.OFF),
                {"is_volume_muted": restored_mute},
            )
        ],
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.persang_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is restored_mute


@pytest.mark.usefixtures("init_integration")
async def test_mute_is_written_to_the_restore_store(hass: HomeAssistant) -> None:
    """Test mute is stored as extra restore data on shutdown."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )

    data = await async_mock_restore_state_shutdown_restart(hass)

    stored_state = data.last_states[MEDIA_PLAYER_ENTITY_ID]
    assert stored_state.extra_data
    assert stored_state.extra_data.as_dict() == {"is_volume_muted": True}


@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test the media player becomes unavailable when the IR entity is."""
    await assert_availability_follows_source_entity(
        hass, MEDIA_PLAYER_ENTITY_ID, MOCK_INFRARED_EMITTER_ENTITY_ID
    )
