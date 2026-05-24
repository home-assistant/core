"""Tests for the Kaku RC switch platform."""

from unittest.mock import patch

from homeassistant.components.klik_aan_klik_uit_rc.const import REPEAT_COUNT
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
    """Return the only Kaku switch entity id from the state machine."""
    entity_ids = [
        entity_id
        for entity_id in hass.states.async_entity_ids(SWITCH_DOMAIN)
        if "kaku" in entity_id
    ]
    assert len(entity_ids) == 1
    return entity_ids[0]


async def test_turn_on_off_sends_kaku_commands(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_klik_aan_klik_uit_rc: MockConfigEntry,
) -> None:
    """Test turning switch on/off sends commands and updates state."""
    entity_id = _switch_entity_id(hass)
    context = Context()

    with patch(
        "homeassistant.components.klik_aan_klik_uit_rc.switch.get_kaku_timings",
        return_value=[275, -275, 275, -1375],
    ) as mock_timings:
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

        first_call = mock_timings.call_args_list[0]
        assert first_call.kwargs["on"] is True
        assert first_call.kwargs["frame_repeats"] == REPEAT_COUNT

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

        second_call = mock_timings.call_args_list[1]
        assert second_call.kwargs["on"] is False
        assert second_call.kwargs["frame_repeats"] == REPEAT_COUNT
