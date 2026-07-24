"""Tests for the LG Infrared select platform."""

from unittest.mock import patch

from infrared_protocols.codes.lg.ac import LgAcButton
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lg_infrared.const import LGDeviceType
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, mock_restore_cache, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity

_ENTITY_ID = "select.lg_ac_energy_limit"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.SELECT]


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
    """Test the select entity is created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("option", "expected_button"),
    [
        pytest.param("off", LgAcButton.ENERGY_LIMIT_OFF, id="off"),
        pytest.param("40", LgAcButton.ENERGY_LIMIT_40, id="40"),
        pytest.param("60", LgAcButton.ENERGY_LIMIT_60, id="60"),
        pytest.param("80", LgAcButton.ENERGY_LIMIT_80, id="80"),
    ],
)
async def test_select_option_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    option: str,
    expected_button: LgAcButton,
) -> None:
    """Test selecting an energy cap sends the matching IR code."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: _ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_button.to_command().get_raw_timings()

    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.state == option


async def test_state_restored_on_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
) -> None:
    """Test the assumed selection is restored after a restart."""
    mock_restore_cache(hass, [State(_ENTITY_ID, "60")])
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lg_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.state == "60"


@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_emitter(hass: HomeAssistant) -> None:
    """Test select availability follows the infrared emitter."""
    await assert_availability_follows_source_entity(hass, _ENTITY_ID, EMITTER_ENTITY_ID)
