"""Tests for the Panasonic Window A/C climate platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.panasonic_window_ac_hk.command import (
    PanasonicWindowAcHKCommand,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity

ENTITY_ID = "climate.panasonic_window_ac_hong_kong"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.CLIMATE]


def _full_timings(**kwargs) -> list[int]:
    """Return the raw timings for an expected full state frame."""
    return PanasonicWindowAcHKCommand.full(**kwargs).get_raw_timings()


@pytest.mark.usefixtures("init_integration")
async def test_initial_state(hass: HomeAssistant) -> None:
    """Test the climate entity starts powered off with the expected options."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.HEAT,
    ]
    assert state.attributes["fan_modes"] == [
        "auto",
        "low",
        "mediumLow",
        "medium",
        "mediumHigh",
        "high",
    ]
    assert state.attributes["swing_modes"] == ["auto", "fixed"]
    assert state.attributes["target_temp_step"] == 0.5
    assert state.attributes["min_temp"] == 16
    assert state.attributes["max_temp"] == 30


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_sends_full_frame(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test selecting an HVAC mode powers on and sends the full state frame."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == HVACMode.COOL
    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert command.modulation == 38000
    assert command.get_raw_timings() == _full_timings(
        off=False,
        mode="cool",
        temp=24.0,
        fan="auto",
        swing="auto",
        nanoex=False,
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_attributes_while_on(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test temperature/fan/swing changes re-send the full frame while on."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "high"},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "fixed"},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TEMPERATURE] == 22.5
    assert state.attributes[ATTR_FAN_MODE] == "high"
    assert state.attributes[ATTR_SWING_MODE] == "fixed"

    timings = [
        c.get_raw_timings() for c in mock_infrared_emitter_entity.send_command_calls
    ]
    assert timings == [
        _full_timings(
            off=False, mode="cool", temp=22.5, fan="auto", swing="auto", nanoex=False
        ),
        _full_timings(
            off=False, mode="cool", temp=22.5, fan="high", swing="auto", nanoex=False
        ),
        _full_timings(
            off=False, mode="cool", temp=22.5, fan="high", swing="fixed", nanoex=False
        ),
    ]


@pytest.mark.usefixtures("init_integration")
async def test_set_attributes_while_off_does_not_send(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test changing options while off updates state but sends nothing."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 18.0},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "low"},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "fixed"},
        blocking=True,
    )

    assert not mock_infrared_emitter_entity.send_command_calls
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 18.0
    assert state.attributes[ATTR_FAN_MODE] == "low"
    assert state.attributes[ATTR_SWING_MODE] == "fixed"


@pytest.mark.usefixtures("init_integration")
async def test_turn_off_sends_off_frame(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test turning off sends an off frame."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == HVACMode.OFF
    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings() == (
        _full_timings(
            off=True, mode="cool", temp=24.0, fan="auto", swing="auto", nanoex=False
        )
    )


@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_emitter(hass: HomeAssistant) -> None:
    """Test the climate entity follows the infrared emitter availability."""
    await assert_availability_follows_source_entity(hass, ENTITY_ID, EMITTER_ENTITY_ID)


@pytest.mark.parametrize(
    "restored_state",
    [
        pytest.param(HVACMode.COOL, id="restored_on"),
        pytest.param(HVACMode.OFF, id="restored_off"),
    ],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_state_restored_on_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    restored_state: HVACMode,
) -> None:
    """Test the assumed state is restored from the previous run."""
    mock_restore_cache(
        hass,
        (
            State(
                ENTITY_ID,
                restored_state,
                {
                    ATTR_TEMPERATURE: 22.5,
                    ATTR_FAN_MODE: "high",
                    ATTR_SWING_MODE: "fixed",
                },
            ),
        ),
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.panasonic_window_ac_hk.PLATFORMS",
        [Platform.CLIMATE],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == restored_state
    assert state.attributes[ATTR_TEMPERATURE] == 22.5
    assert state.attributes[ATTR_FAN_MODE] == "high"
    assert state.attributes[ATTR_SWING_MODE] == "fixed"
