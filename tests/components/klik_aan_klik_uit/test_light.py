"""Tests for the Kaku RC light platform."""

from unittest.mock import patch

from homeassistant.components.klik_aan_klik_uit.const import REPEAT_COUNT
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity


def _light_entity_id(hass: HomeAssistant) -> str:
    """Return the only Kaku light entity id from the state machine."""
    entity_ids = [
        entity_id
        for entity_id in hass.states.async_entity_ids(LIGHT_DOMAIN)
        if "kaku" in entity_id
    ]
    assert len(entity_ids) == 1
    return entity_ids[0]


async def test_dim_turn_on_off_sends_kaku_commands(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_klik_aan_klik_uit_dim: MockConfigEntry,
) -> None:
    """Test dim light on/off sends commands and updates state."""
    entity_id = _light_entity_id(hass)
    context = Context()

    with patch(
        "homeassistant.components.klik_aan_klik_uit.light.KakuCommand",
    ) as mock_command:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
            context=context,
            blocking=True,
        )

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_ON
        assert state.attributes[ATTR_BRIGHTNESS] == 255
        assert len(mock_rf_entity.send_command_calls) == 1

        first_call = mock_command.call_args_list[0]
        assert first_call.kwargs["on"] is None
        assert first_call.kwargs["dimlevel"] == 100
        assert first_call.kwargs["frame_repeats"] == REPEAT_COUNT

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            context=context,
            blocking=True,
        )

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF
        assert len(mock_rf_entity.send_command_calls) == 2

        second_call = mock_command.call_args_list[1]
        assert second_call.kwargs["on"] is False
        assert second_call.kwargs["dimlevel"] is None
        assert second_call.kwargs["frame_repeats"] == REPEAT_COUNT


async def test_mid_brightness_maps_to_percent(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_klik_aan_klik_uit_dim: MockConfigEntry,
) -> None:
    """Test HA brightness 128 is mapped to Kaku dimlevel 50."""
    entity_id = _light_entity_id(hass)

    with patch(
        "homeassistant.components.klik_aan_klik_uit.light.KakuCommand",
    ) as mock_command:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
            blocking=True,
        )

        first_call = mock_command.call_args_list[0]
        assert first_call.kwargs["on"] is None
        assert first_call.kwargs["dimlevel"] == 50
