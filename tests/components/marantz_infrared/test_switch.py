"""Tests for the Marantz Infrared switch platform."""

from infrared_protocols.codes.marantz.audio import MarantzAudioCode
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

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform, TargetKey
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

PM8006 = "pm8006_integrated_amplifier"
SWITCH_ENTITY_ID_SPEAKER_A = "switch.marantz_pm8006_integrated_amplifier_speaker_a"
SWITCH_ENTITY_ID_SPEAKER_B = "switch.marantz_pm8006_integrated_amplifier_speaker_b"
SWITCH_ENTITY_ID_POWER_AMP_DIRECT = (
    "switch.marantz_pm8006_integrated_amplifier_power_amp_direct"
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.SWITCH]


@pytest.mark.parametrize("model", [PM8006], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all switch entities are created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("model", [PM8006], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "on_code", "off_code"),
    [
        (
            SWITCH_ENTITY_ID_SPEAKER_A,
            MarantzAudioCode.SPEAKER_A_ON,
            MarantzAudioCode.SPEAKER_A_OFF,
        ),
        (
            SWITCH_ENTITY_ID_SPEAKER_B,
            MarantzAudioCode.SPEAKER_B_ON,
            MarantzAudioCode.SPEAKER_B_OFF,
        ),
        (
            SWITCH_ENTITY_ID_POWER_AMP_DIRECT,
            MarantzAudioCode.POWER_AMP_DIRECT_ON,
            MarantzAudioCode.POWER_AMP_DIRECT_OFF,
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_turn_on_off_sends_code_and_sets_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    on_code: MarantzAudioCode,
    off_code: MarantzAudioCode,
) -> None:
    """Test turning a switch on and off sends its codes and updates the state."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    assert mock_infrared_emitter_entity.send_command_calls == [on_code, off_code]


@pytest.mark.usefixtures("init_integration")
async def test_only_supported_switches_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a model without the discrete codes gets no switches."""
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


@pytest.mark.parametrize("model", [PM8006], indirect=True)
@pytest.mark.parametrize("restored_state", [STATE_ON, STATE_OFF])
@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_marantz_to_command")
async def test_restores_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    restored_state: str,
) -> None:
    """Test the assumed state survives a restart."""
    mock_restore_cache(hass, [State(SWITCH_ENTITY_ID_POWER_AMP_DIRECT, restored_state)])
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID_POWER_AMP_DIRECT)
    assert state is not None
    assert state.state == restored_state


@pytest.mark.parametrize("model", [PM8006], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_switch_availability_follows_ir_entity(hass: HomeAssistant) -> None:
    """Test switch becomes unavailable when IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, SWITCH_ENTITY_ID_POWER_AMP_DIRECT, [MOCK_INFRARED_EMITTER_ENTITY_ID]
    )
