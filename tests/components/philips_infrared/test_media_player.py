"""Tests for the Philips Infrared media player platform."""

from unittest.mock import MagicMock, patch

from infrared_protocols.codes.philips.tv import PhilipsTVCode
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    mock_restore_cache,
    snapshot_platform,
)
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    MediaPlayerState,
)
from homeassistant.components.philips_infrared.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

MEDIA_PLAYER_ENTITY_ID = "media_player.philips_tv"


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the media player entity is created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify entity belongs to the correct device
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("service", "service_data", "expected_code"),
    [
        (SERVICE_VOLUME_UP, {}, PhilipsTVCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, {}, PhilipsTVCode.VOLUME_DOWN),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, PhilipsTVCode.MUTE),
        (SERVICE_MEDIA_NEXT_TRACK, {}, PhilipsTVCode.CHANNEL_UP),
        (SERVICE_MEDIA_PREVIOUS_TRACK, {}, PhilipsTVCode.CHANNEL_DOWN),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    service_data: dict[str, bool],
    expected_code: PhilipsTVCode,
) -> None:
    """Test each media player action sends the correct IR code."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, **service_data},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0] == expected_code
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "restored_states",
    [
        pytest.param([], id="unknown"),
        pytest.param([State(MEDIA_PLAYER_ENTITY_ID, MediaPlayerState.OFF)], id="off"),
    ],
)
@pytest.mark.parametrize(
    ("service", "expected_code", "expected_state"),
    [
        (SERVICE_TURN_ON, PhilipsTVCode.POWER, MediaPlayerState.ON),
        (SERVICE_TURN_OFF, PhilipsTVCode.POWER, MediaPlayerState.OFF),
        (SERVICE_MEDIA_PLAY, PhilipsTVCode.PLAY, MediaPlayerState.PLAYING),
        (SERVICE_MEDIA_PAUSE, PhilipsTVCode.PAUSE, MediaPlayerState.PAUSED),
        (SERVICE_MEDIA_STOP, PhilipsTVCode.STOP, MediaPlayerState.IDLE),
        (SERVICE_MEDIA_PLAY_PAUSE, PhilipsTVCode.PLAY, MediaPlayerState.PLAYING),
    ],
)
@pytest.mark.usefixtures("mock_philips_to_command")
async def test_state_changing_commands(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    restored_states: list[State],
    service: str,
    expected_code: PhilipsTVCode,
    expected_state: MediaPlayerState,
) -> None:
    """Test commands send a code and update the assumed state, even when off."""
    await _setup_with_restored_states(
        hass, mock_config_entry, platforms, restored_states
    )

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


@pytest.mark.usefixtures("init_integration")
async def test_play_pause_alternates(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test consecutive play/pause calls alternate between play and pause."""
    for _ in range(3):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PLAY_PAUSE,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
            blocking=True,
        )

    assert mock_infrared_emitter_entity.send_command_calls == [
        PhilipsTVCode.PLAY,
        PhilipsTVCode.PAUSE,
        PhilipsTVCode.PLAY,
    ]


@pytest.mark.parametrize(
    "restored_state",
    [
        MediaPlayerState.ON,
        MediaPlayerState.OFF,
        MediaPlayerState.PLAYING,
        MediaPlayerState.PAUSED,
        MediaPlayerState.IDLE,
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
    await _setup_with_restored_states(
        hass,
        mock_config_entry,
        platforms,
        [State(MEDIA_PLAYER_ENTITY_ID, restored_state)],
    )

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.state == restored_state


async def _setup_with_restored_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
    restored_states: list[State],
) -> None:
    """Set up the integration with the given states in the restore cache."""
    mock_restore_cache(hass, restored_states)

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.philips_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("init_integration")
async def test_toggle_flips_between_commands(
    hass: HomeAssistant,
    mock_philips_to_command: MagicMock,
) -> None:
    """The RC-6 toggle bit must alternate so the TV sees distinct presses."""
    for _ in range(4):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_UP,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
            blocking=True,
        )

    toggles = [call.kwargs["toggle"] for call in mock_philips_to_command.call_args_list]
    assert toggles == [1, 0, 1, 0]


@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test media player becomes unavailable when IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, MEDIA_PLAYER_ENTITY_ID, [MOCK_INFRARED_EMITTER_ENTITY_ID]
    )
