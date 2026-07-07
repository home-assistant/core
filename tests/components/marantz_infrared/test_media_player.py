"""Tests for the Marantz Infrared media player platform."""

from typing import Any
from unittest.mock import MagicMock

from infrared_protocols.codes.marantz.audio import MarantzAudioCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID, media_player_entity_id

from tests.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared.common import MockInfraredEmitterEntity

MEDIA_PLAYER_ENTITY_ID = "media_player.marantz_pm6006_integrated_amplifier"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.MEDIA_PLAYER]


@pytest.mark.parametrize(
    "model",
    ["pm6006_integrated_amplifier", "sr_7000_receiver"],
    indirect=True,
)
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

    device_entry = device_registry.async_get_device(
        identifiers={("marantz_infrared", mock_config_entry.entry_id)}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("model", "has_select_source"),
    [
        ("pm6006_integrated_amplifier", True),
        ("sr_7000_receiver", False),
    ],
    indirect=["model"],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_source_feature_matches_model(
    hass: HomeAssistant,
    model: str,
    has_select_source: bool,
) -> None:
    """SELECT_SOURCE is advertised only when the model has source codes."""
    state = hass.states.get(media_player_entity_id(model))
    assert state is not None
    features = state.attributes["supported_features"]
    assert bool(features & MediaPlayerEntityFeature.SELECT_SOURCE) is has_select_source


@pytest.mark.parametrize(
    ("service", "service_data", "expected_code"),
    [
        (SERVICE_TURN_ON, {}, MarantzAudioCode.POWER_ON),
        (SERVICE_TURN_OFF, {}, MarantzAudioCode.POWER_OFF),
        (SERVICE_VOLUME_UP, {}, MarantzAudioCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, {}, MarantzAudioCode.VOLUME_DOWN),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, MarantzAudioCode.MUTE_ON),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": False}, MarantzAudioCode.MUTE_OFF),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    service_data: dict[str, bool],
    expected_code: MarantzAudioCode,
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


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        ("cd", MarantzAudioCode.SOURCE_CD),
        ("recorder", MarantzAudioCode.SOURCE_CDR),
        ("phono", MarantzAudioCode.SOURCE_PHONO),
        ("tuner", MarantzAudioCode.SOURCE_TUNER),
        ("coax", MarantzAudioCode.SOURCE_COAX),
        ("network", MarantzAudioCode.SOURCE_NETWORK),
        ("optical", MarantzAudioCode.SOURCE_OPTICAL),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_select_source(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    source: str,
    expected_code: MarantzAudioCode,
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
        "cd",
        "coax",
        "network",
        "optical",
        "phono",
        "recorder",
        "tuner",
    ]


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_off_update_assumed_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Turn-on sends POWER_ON and turn-off sends POWER_OFF."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == "on"

    assert mock_infrared_emitter_entity.send_command_calls == [
        MarantzAudioCode.POWER_OFF,
        MarantzAudioCode.POWER_ON,
    ]


@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test media player becomes unavailable when IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, MEDIA_PLAYER_ENTITY_ID, MOCK_INFRARED_EMITTER_ENTITY_ID
    )


async def _setup_with_restore(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    restored: State,
    extra_data: dict[str, Any],
) -> None:
    """Seed the restore cache (state + extra data) and set up the integration."""
    mock_restore_cache_with_extra_data(hass, [(restored, extra_data)])
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "restored_state",
    [MediaPlayerState.ON, MediaPlayerState.OFF],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_marantz_to_command")
async def test_restores_state_source_and_mute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    restored_state: MediaPlayerState,
) -> None:
    """State, source, and mute survive a restart even from the OFF state.

    Source/mute are persisted via extra-restore data so the OFF case
    (where the base class strips them from state attributes) still
    restores them — the user sees the previously-selected source the
    moment they turn the amp back on.
    """
    await _setup_with_restore(
        hass,
        mock_config_entry,
        State(MEDIA_PLAYER_ENTITY_ID, restored_state),
        extra_data={"source": "phono", "is_volume_muted": True},
    )

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == restored_state.value

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes[ATTR_INPUT_SOURCE] == "phono"
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is True


@pytest.mark.usefixtures("init_integration")
async def test_initial_state_unknown_when_no_restore(hass: HomeAssistant) -> None:
    """With no previous state to restore, the entity reports unknown."""
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_INPUT_SOURCE) is None
    assert state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is None


@pytest.mark.usefixtures("init_integration")
async def test_toggle_flips_between_commands(
    hass: HomeAssistant,
    mock_marantz_to_command: MagicMock,
) -> None:
    """The RC-5 toggle bit must alternate so the receiver sees distinct presses."""
    for _ in range(4):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_UP,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
            blocking=True,
        )

    toggles = [call.kwargs["toggle"] for call in mock_marantz_to_command.call_args_list]
    assert toggles == [1, 0, 1, 0]


@pytest.mark.usefixtures("init_integration")
async def test_power_on_sends_repeat_count(
    hass: HomeAssistant,
    mock_marantz_to_command: MagicMock,
) -> None:
    """Power-on sends repeat_count=5 so the receiver reliably wakes up."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    assert mock_marantz_to_command.call_count == 1
    assert mock_marantz_to_command.call_args_list[0].kwargs["repeat_count"] == 5
