"""Tests for the LG Infrared switch platform."""

from unittest.mock import patch

from infrared_protocols.codes.lg.ac import LGACCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lg_infrared.const import LGDeviceType
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, mock_restore_cache, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity

_ION_ENTITY_ID = "switch.lg_ac_ion_generator"
_AUTO_CLEAN_ENTITY_ID = "switch.lg_ac_auto_clean"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.SWITCH]


@pytest.fixture
def device_type() -> LGDeviceType:
    """Return the device type of the config entry."""
    return LGDeviceType.AC


@pytest.fixture
def has_receiver() -> bool:
    """Return whether the config entry has an infrared receiver configured."""
    return False


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all switch entities are created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "on_code", "off_code"),
    [
        pytest.param(
            _ION_ENTITY_ID,
            LGACCode.ION_GENERATOR_ON,
            LGACCode.ION_GENERATOR_OFF,
            id="ion",
        ),
        pytest.param(
            _AUTO_CLEAN_ENTITY_ID,
            LGACCode.AUTO_CLEAN_ON,
            LGACCode.AUTO_CLEAN_OFF,
            id="auto_clean",
        ),
    ],
)
async def test_switch_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    on_code: LGACCode,
    off_code: LGACCode,
) -> None:
    """Test turning a switch on and off sends the matching discrete IR codes."""
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == on_code.to_command().get_raw_timings()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 2
    timings = mock_infrared_emitter_entity.send_command_calls[1].get_raw_timings()
    assert timings == off_code.to_command().get_raw_timings()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


async def test_state_restored_on_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
) -> None:
    """Test the assumed on/off state is restored after a restart."""
    mock_restore_cache(hass, [State(_ION_ENTITY_ID, STATE_ON)])
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lg_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_ION_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_emitter(hass: HomeAssistant) -> None:
    """Test switch availability follows the infrared emitter."""
    await assert_availability_follows_source_entity(
        hass, _ION_ENTITY_ID, EMITTER_ENTITY_ID
    )
