"""Tests for the Marantz Infrared media player platform."""

from typing import Any

from infrared_protocols.codes.marantz.audio import MarantzAudioCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.infrared import (
    DATA_COMPONENT as INFRARED_DATA_COMPONENT,
    DOMAIN as INFRARED_DOMAIN,
)
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
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import MockInfraredEntity
from .utils import check_availability_follows_ir_entity

from tests.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)

MEDIA_PLAYER_ENTITY_ID = "media_player.marantz_pm6006_integrated_amplifier"


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
    ("service", "service_data", "expected_code"),
    [
        (SERVICE_TURN_ON, {}, MarantzAudioCode.POWER),
        (SERVICE_TURN_OFF, {}, MarantzAudioCode.POWER),
        (SERVICE_VOLUME_UP, {}, MarantzAudioCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, {}, MarantzAudioCode.VOLUME_DOWN),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, MarantzAudioCode.MUTE),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_entity: MockInfraredEntity,
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

    assert len(mock_infrared_entity.send_command_calls) == 1
    assert mock_infrared_entity.send_command_calls[0] == expected_code


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
    mock_infrared_entity: MockInfraredEntity,
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

    assert mock_infrared_entity.send_command_calls == [expected_code]

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
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Both turn-on and turn-off send POWER but assume opposite states."""
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

    assert mock_infrared_entity.send_command_calls == [
        MarantzAudioCode.POWER,
        MarantzAudioCode.POWER,
    ]


@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test media player becomes unavailable when IR entity is unavailable."""
    await check_availability_follows_ir_entity(hass, MEDIA_PLAYER_ENTITY_ID)


async def _setup_with_restore(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_entity: MockInfraredEntity,
    restored: State,
    extra_data: dict[str, Any],
) -> None:
    """Seed the restore cache (state + extra data) and set up the integration."""
    mock_restore_cache_with_extra_data(hass, [(restored, extra_data)])
    assert await async_setup_component(hass, INFRARED_DOMAIN, {})
    await hass.async_block_till_done()
    await hass.data[INFRARED_DATA_COMPONENT].async_add_entities([mock_infrared_entity])
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "restored_state",
    [MediaPlayerState.ON, MediaPlayerState.OFF],
)
async def test_restores_state_source_and_mute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_entity: MockInfraredEntity,
    mock_marantz_to_command: None,
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
        mock_infrared_entity,
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


async def test_toggle_flips_between_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """The RC-5 toggle bit must alternate so the receiver sees distinct presses."""
    for expected_toggle in (1, 0, 1, 0):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_UP,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
            blocking=True,
        )
        assert init_integration.runtime_data.toggle == expected_toggle

    assert len(mock_infrared_entity.send_command_calls) == 4
