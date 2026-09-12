"""Tests for the Intertechno TriState switch platform."""

from rf_protocols.commands.pt2262 import PT2262Command

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity


def _switch_entity_id(hass: HomeAssistant) -> str:
    """Return the only Intertechno switch entity id from the state machine."""
    entity_ids = [
        entity_id
        for entity_id in hass.states.async_entity_ids(SWITCH_DOMAIN)
        if "intertechno" in entity_id
    ]
    assert len(entity_ids) == 1
    return entity_ids[0]


async def test_turn_on_off_sends_pt2262_commands(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_intertechno_tristate: MockConfigEntry,
) -> None:
    """Test switch on/off behavior."""
    entity_id = _switch_entity_id(hass)
    context = Context()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        context=context,
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert len(mock_rf_entity.send_command_calls) == 1

    first_command = mock_rf_entity.send_command_calls[0].command
    assert isinstance(first_command, PT2262Command)
    assert len(first_command.data) == 12
    assert set(first_command.data).issubset({"0", "1", "F"})
    assert first_command.repeat_count == 5

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        context=context,
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert len(mock_rf_entity.send_command_calls) == 2

    second_command = mock_rf_entity.send_command_calls[1].command
    assert isinstance(second_command, PT2262Command)
    assert len(second_command.data) == 12
    assert set(second_command.data).issubset({"0", "1", "F"})
    assert second_command.repeat_count == 5
    assert second_command.data != first_command.data
