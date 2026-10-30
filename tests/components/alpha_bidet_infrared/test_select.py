"""Tests for the Alpha Bidet Infrared select platform."""

from unittest.mock import patch

from infrared_protocols.codes.alpha_bidet.jx2 import AlphaBidetJX2LevelCode
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

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import async_get as async_get_restore_state

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

WATER_TEMPERATURE_ENTITY_ID = "select.alpha_bidet_jx2_water_temperature"
SEAT_TEMPERATURE_ENTITY_ID = "select.alpha_bidet_jx2_seat_temperature"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.SELECT]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the select entities are created with the correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "level_code"),
    [
        (WATER_TEMPERATURE_ENTITY_ID, AlphaBidetJX2LevelCode.WATER_TEMP),
        (SEAT_TEMPERATURE_ENTITY_ID, AlphaBidetJX2LevelCode.SEAT_TEMP),
    ],
)
@pytest.mark.parametrize(
    ("option", "level"), [("off", 0), ("low", 1), ("medium", 2), ("high", 3)]
)
@pytest.mark.usefixtures("init_integration")
async def test_select_option_sends_absolute_level(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    level_code: AlphaBidetJX2LevelCode,
    option: str,
    level: int,
) -> None:
    """Test selecting a level sends that level, not a step from the current one."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == level_code.to_command(level).get_raw_timings()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == option


@pytest.mark.parametrize(
    ("restored_state", "restored_option", "expected_state"),
    [
        pytest.param("medium", "medium", "medium", id="available"),
        pytest.param(STATE_UNAVAILABLE, "medium", "medium", id="unavailable"),
        pytest.param("bogus", "bogus", STATE_UNKNOWN, id="unknown_option"),
    ],
)
async def test_state_restored_on_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    restored_state: str,
    restored_option: str,
    expected_state: str,
) -> None:
    """Test the last level sent is restored, even if the select was unavailable."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(WATER_TEMPERATURE_ENTITY_ID, restored_state),
                {"current_option": restored_option},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.alpha_bidet_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(WATER_TEMPERATURE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("init_integration")
async def test_option_stored_while_unavailable(hass: HomeAssistant) -> None:
    """Test the last level sent is stored while the emitter is unavailable."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: WATER_TEMPERATURE_ENTITY_ID, ATTR_OPTION: "medium"},
        blocking=True,
    )
    hass.states.async_set(MOCK_INFRARED_EMITTER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(WATER_TEMPERATURE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    stored = {
        stored.state.entity_id: stored
        for stored in async_get_restore_state(hass).async_get_stored_states()
    }
    extra_data = stored[WATER_TEMPERATURE_ENTITY_ID].extra_data
    assert extra_data is not None
    assert extra_data.as_dict() == {"current_option": "medium"}


@pytest.mark.usefixtures("init_integration")
async def test_select_availability_follows_ir_entity(hass: HomeAssistant) -> None:
    """Test a select becomes unavailable when the IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, WATER_TEMPERATURE_ENTITY_ID, [MOCK_INFRARED_EMITTER_ENTITY_ID]
    )
