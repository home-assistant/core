"""Tests for the Novy Hood fan platform."""

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    DOMAIN as FAN_DOMAIN,
    SERVICE_DECREASE_SPEED,
    SERVICE_INCREASE_SPEED,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ASSUMED_STATE, ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant, State

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

ENTITY_ID = "fan.novy_cooker_hood"


async def test_turn_on_calibrates_to_level_1(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_cooker_hood: MockConfigEntry,
) -> None:
    """Default turn_on sends 4 minus + 1 plus and lands at 25%."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ASSUMED_STATE] is True

    context = Context()
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        context=context,
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 25
    assert len(mock_rf_entity.send_command_calls) == 5
    assert all(c.context is context for c in mock_rf_entity.send_command_calls)


async def test_turn_on_with_percentage_calibrates_to_level(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_cooker_hood: MockConfigEntry,
) -> None:
    """turn_on with percentage targets the matching level via calibration."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 50},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 50
    assert len(mock_rf_entity.send_command_calls) == 6


async def test_set_percentage_zero_turns_off(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_cooker_hood: MockConfigEntry,
) -> None:
    """set_percentage(0) turns the fan off via the calibration sequence."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 0
    assert len(mock_rf_entity.send_command_calls) == 4


async def test_turn_off_sends_four_minuses(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_cooker_hood: MockConfigEntry,
) -> None:
    """turn_off sends 4 minus presses."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 0
    assert len(mock_rf_entity.send_command_calls) == 4


async def test_set_percentage_calibrates(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_cooker_hood: MockConfigEntry,
) -> None:
    """set_percentage(75) sends 4 minus + 3 plus and lands at level 3."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 75},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 75
    assert len(mock_rf_entity.send_command_calls) == 7


async def test_increase_speed_sends_single_plus(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_cooker_hood: MockConfigEntry,
) -> None:
    """increase_speed sends one plus and bumps level by one (no recalibration)."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 25
    assert len(mock_rf_entity.send_command_calls) == 1


async def test_increase_speed_clamps_at_max(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Pressing increase at level 4 still sends the RF press but clamps level."""
    mock_restore_cache(
        hass, [State(ENTITY_ID, STATE_ON, attributes={ATTR_PERCENTAGE: 100})]
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PERCENTAGE] == 100
    assert len(mock_rf_entity.send_command_calls) == 1


async def test_decrease_speed_sends_single_minus(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """decrease_speed sends one minus and drops level by one."""
    mock_restore_cache(
        hass, [State(ENTITY_ID, STATE_ON, attributes={ATTR_PERCENTAGE: 50})]
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PERCENTAGE] == 25
    assert len(mock_rf_entity.send_command_calls) == 1


async def test_increase_speed_with_step_sends_n_presses(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_cooker_hood: MockConfigEntry,
) -> None:
    """increase_speed with percentage_step sends N plus presses (no recalibration)."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE_STEP: 50},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PERCENTAGE] == 50
    assert len(mock_rf_entity.send_command_calls) == 2


async def test_decrease_speed_with_step_sends_n_presses(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """decrease_speed with percentage_step sends N minus presses (no recalibration)."""
    mock_restore_cache(
        hass, [State(ENTITY_ID, STATE_ON, attributes={ATTR_PERCENTAGE: 100})]
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE_STEP: 50},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PERCENTAGE] == 50
    assert len(mock_rf_entity.send_command_calls) == 2


async def test_decrease_speed_clamps_at_off(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_cooker_hood: MockConfigEntry,
) -> None:
    """decrease_speed at level 0 still sends one minus but level stays at 0."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert len(mock_rf_entity.send_command_calls) == 1


async def test_restore_state(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The fan restores its previous percentage without sending commands."""
    mock_restore_cache(
        hass, [State(ENTITY_ID, STATE_ON, attributes={ATTR_PERCENTAGE: 50})]
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 50
    assert mock_rf_entity.send_command_calls == []
