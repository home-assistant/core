"""Tests for the Vacmaster Cardio54 fan platform."""

from __future__ import annotations

import pytest

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.vacmaster_cardio54.const import (
    DATA_POWER,
    DATA_SPEEDS,
    DEVICE_ID_BITS,
    FRAME_REPEATS,
    FREQUENCY,
    MODULATION,
    TIMEBASE_US,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

ENTITY_ID = "fan.vacmaster_cardio54"


def _last_command_data(mock_rf_entity: MockRadioFrequencyEntity) -> int:
    """Return the EV1527 data nibble of the most recent send."""
    return mock_rf_entity.send_command_calls[-1].command.data


def _assert_command_shape(mock_rf_entity: MockRadioFrequencyEntity) -> None:
    """Sanity-check the protocol fields of every send."""
    for call in mock_rf_entity.send_command_calls:
        cmd = call.command
        assert cmd.frequency == FREQUENCY
        assert cmd.modulation == MODULATION
        # rf_protocols repeat_count is *additional* sends.
        assert cmd.repeat_count == FRAME_REPEATS
        assert cmd.timebase_us == TIMEBASE_US
        assert 0 <= cmd.device_id < (1 << DEVICE_ID_BITS)
        assert 0 <= cmd.data <= 0xF


async def test_turn_on_defaults_to_speed_one(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_vacmaster_cardio54: MockConfigEntry,
) -> None:
    """``fan.turn_on`` without a percentage sends speed I (33%)."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 33

    assert len(mock_rf_entity.send_command_calls) == 1
    assert _last_command_data(mock_rf_entity) == DATA_SPEEDS[0]
    _assert_command_shape(mock_rf_entity)


@pytest.mark.parametrize(
    ("percentage", "expected_level"),
    [
        (33, 1),  # 33% -> ceil(0.99) = 1
        (50, 2),  # 50% -> ceil(1.5)  = 2
        (66, 2),  # 66% -> ceil(1.98) = 2
        (67, 3),  # 67% -> ceil(2.01) = 3
        (100, 3),
    ],
)
async def test_turn_on_percentage_maps_to_level(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_vacmaster_cardio54: MockConfigEntry,
    percentage: int,
    expected_level: int,
) -> None:
    """``fan.turn_on percentage=X`` selects the right of the 3 speed nibbles."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    assert len(mock_rf_entity.send_command_calls) == 1
    assert _last_command_data(mock_rf_entity) == DATA_SPEEDS[expected_level - 1]


async def test_set_percentage_changes_speed(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_vacmaster_cardio54: MockConfigEntry,
) -> None:
    """``fan.set_percentage`` sends the new speed nibble and updates state."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 100},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 100
    assert _last_command_data(mock_rf_entity) == DATA_SPEEDS[2]


async def test_set_percentage_zero_turns_off_when_on(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_vacmaster_cardio54: MockConfigEntry,
) -> None:
    """``set_percentage 0`` sends the power toggle when the fan was on."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert len(mock_rf_entity.send_command_calls) == 1

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 0
    assert len(mock_rf_entity.send_command_calls) == 2
    assert _last_command_data(mock_rf_entity) == DATA_POWER


async def test_turn_off_when_off_sends_nothing(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_vacmaster_cardio54: MockConfigEntry,
) -> None:
    """``turn_off`` on an already-off fan must not send the power toggle.

    The Cardio54's POWER button is a toggle, so re-sending it from the
    assumed-off state would actually switch the fan ON.
    """
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert mock_rf_entity.send_command_calls == []
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_turn_off_when_on_sends_power_toggle(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_vacmaster_cardio54: MockConfigEntry,
) -> None:
    """``turn_off`` on a running fan sends a single POWER toggle."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    assert _last_command_data(mock_rf_entity) == DATA_SPEEDS[2]

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert _last_command_data(mock_rf_entity) == DATA_POWER


async def test_restore_state_rejects_bool_percentage(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """``ATTR_PERCENTAGE=True`` must not be treated as percentage 1.

    ``bool`` subclasses ``int`` so a stray ``True`` in the restored
    attributes would otherwise pass ``isinstance(last_pct, (int, float))``
    and bring the fan back at speed 1 — visible to the user when the
    previous ``state`` was anything other than ``on`` (the ``STATE_ON``
    fallback for missing percentages would mask the bug otherwise). Last
    state ``off`` here makes the bug-vs-fix difference observable.
    """
    mock_restore_cache(
        hass,
        [
            State(
                ENTITY_ID,
                STATE_OFF,
                attributes={ATTR_PERCENTAGE: True},
            )
        ],
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    # Bool rejected -> _level stayed 0 -> fan presents as off (matches the
    # restored ``off`` state). Without the guard the fan would silently
    # come back at speed 1.
    assert state.state == STATE_OFF


async def test_restore_state_clamps_corrupted_percentage(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """``ATTR_PERCENTAGE > 100`` must clamp ``_level`` to ``SPEED_COUNT``.

    Without the clamp ``math.ceil(percentage_to_ranged_value((1, 3), 150))``
    returns 5, which would index past ``DATA_SPEEDS`` on the next
    ``turn_on`` and raise ``IndexError``. Clamping keeps the fan at the
    top valid speed instead.
    """
    mock_restore_cache(
        hass,
        [
            State(
                ENTITY_ID,
                STATE_ON,
                attributes={ATTR_PERCENTAGE: 150},
            )
        ],
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    # Clamped to SPEED_COUNT=3 -> 100% (top of the 1..3 range).
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 100


async def test_restore_state_does_not_transmit(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Restoring a previous percentage must not fire any RF commands."""
    mock_restore_cache(
        hass,
        [
            State(
                ENTITY_ID,
                STATE_ON,
                attributes={ATTR_PERCENTAGE: 66},
            )
        ],
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    # 66% restored -> percentage_to_ranged_value((1, 3), 66) -> ceil(1.98) ->
    # level 2 -> ranged_value_to_percentage((1, 3), 2) -> int(66.67) = 66.
    # The HA helper truncates rather than rounds, so the read-back value is
    # 66% (not 67%).
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 66
    # Crucially: nothing transmitted during restore.
    assert mock_rf_entity.send_command_calls == []


async def test_unavailable_when_transmitter_goes_offline(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_vacmaster_cardio54: MockConfigEntry,
) -> None:
    """The fan flips to unavailable when its transmitter does, and back."""
    transmitter_entity_id = mock_rf_entity.entity_id
    # Mark the transmitter unavailable.
    hass.states.async_set(transmitter_entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE

    # Recovery — radio_frequency entities have no specific "online" state;
    # any non-unavailable value (e.g. ``unknown`` after re-registration)
    # restores availability.
    hass.states.async_set(transmitter_entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE
