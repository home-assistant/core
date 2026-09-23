"""Tests for the Alpha Bidet Infrared select platform."""

from unittest.mock import patch

from infrared_protocols.codes.alpha_bidet.jx2 import AlphaBidetJX2Setting
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

from tests.common import MockConfigEntry, mock_restore_cache, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared.common import MockInfraredEmitterEntity

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
    ("entity_id", "setting"),
    [
        (WATER_TEMPERATURE_ENTITY_ID, AlphaBidetJX2Setting.WATER_TEMP),
        (SEAT_TEMPERATURE_ENTITY_ID, AlphaBidetJX2Setting.SEAT_TEMP),
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
    setting: AlphaBidetJX2Setting,
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
    assert timings == setting.to_command(level).get_raw_timings()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == option


@pytest.mark.parametrize(
    ("restored_state", "expected_state"),
    [("medium", "medium"), ("bogus", STATE_UNKNOWN)],
)
async def test_state_restored_on_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    restored_state: str,
    expected_state: str,
) -> None:
    """Test the assumed level is restored after a restart, ignoring unknown ones."""
    mock_restore_cache(hass, [State(WATER_TEMPERATURE_ENTITY_ID, restored_state)])
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.alpha_bidet_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(WATER_TEMPERATURE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("init_integration")
async def test_select_availability_follows_ir_entity(hass: HomeAssistant) -> None:
    """Test a select becomes unavailable when the IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, WATER_TEMPERATURE_ENTITY_ID, MOCK_INFRARED_EMITTER_ENTITY_ID
    )
