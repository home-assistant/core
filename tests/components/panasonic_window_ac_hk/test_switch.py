"""Tests for the Panasonic Window A/C nanoeX switch platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.panasonic_window_ac_hk.command import (
    PanasonicWindowAcHKCommand,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity

ENTITY_ID = "switch.panasonic_window_ac_hong_kong_nanoex"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.SWITCH]


def _full_timings(**kwargs) -> list[int]:
    """Return the raw timings for an expected full state frame."""
    return PanasonicWindowAcHKCommand.full(**kwargs).get_raw_timings()


@pytest.mark.usefixtures("init_integration")
async def test_initial_state(hass: HomeAssistant) -> None:
    """Test nanoeX starts off."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_off_sends_full_frame(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test toggling nanoeX re-sends the full state frame with the right bit."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings() == (
        _full_timings(
            off=True, mode="cool", temp=24.0, fan="auto", swing="auto", nanoex=True
        )
    )

    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings() == (
        _full_timings(
            off=True, mode="cool", temp=24.0, fan="auto", swing="auto", nanoex=False
        )
    )


@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_emitter(hass: HomeAssistant) -> None:
    """Test the switch follows the infrared emitter availability."""
    await assert_availability_follows_source_entity(hass, ENTITY_ID, EMITTER_ENTITY_ID)


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_nanoex_state_restored_on_restart(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the assumed nanoeX state is restored from the previous run."""
    mock_restore_cache(hass, (State(ENTITY_ID, STATE_ON),))
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.panasonic_window_ac_hk.PLATFORMS",
        [Platform.SWITCH],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON
