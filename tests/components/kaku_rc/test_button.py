"""Tests for the Kaku RC button platform."""

from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.kaku_rc.const import (
    CONF_CHANNEL,
    CONF_DEVICE_ID,
    CONF_DIM,
    CONF_GROUP,
    CONF_TRANSMITTER,
    DOMAIN,
    REPEAT_COUNT_LEARN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity


def _kaku_button_entity_ids(hass: HomeAssistant) -> list[str]:
    """Return Kaku button entity ids from the state machine."""
    return [
        entity_id
        for entity_id in hass.states.async_entity_ids(BUTTON_DOMAIN)
        if "kaku" in entity_id
    ]


async def test_press_buttons_send_kaku_commands(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_kaku_rc: MockConfigEntry,
) -> None:
    """Test pressing learn/unlearn buttons sends commands."""
    entity_ids = _kaku_button_entity_ids(hass)
    assert len(entity_ids) == 2

    learn_entity_id = next(
        entity_id for entity_id in entity_ids if "learn" in entity_id
    )
    unlearn_entity_id = next(
        entity_id for entity_id in entity_ids if "unlearn" in entity_id
    )

    with patch(
        "homeassistant.components.kaku_rc.button.get_kaku_timings",
        return_value=[275, -275, 275, -1375],
    ) as mock_timings:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {"entity_id": learn_entity_id},
            blocking=True,
        )

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {"entity_id": unlearn_entity_id},
            blocking=True,
        )

        assert len(mock_rf_entity.send_command_calls) == 2

        first_call = mock_timings.call_args_list[0]
        assert first_call.kwargs["on"] is True
        assert first_call.kwargs["frame_repeats"] == REPEAT_COUNT_LEARN

        second_call = mock_timings.call_args_list[1]
        assert second_call.kwargs["on"] is False
        assert second_call.kwargs["frame_repeats"] == REPEAT_COUNT_LEARN


async def test_group_entry_does_not_create_buttons(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """Test no buttons are created when group mode is enabled."""
    entity_registry = er.async_get(hass)
    rf_entry = entity_registry.async_get("radio_frequency.test_rf_transmitter")
    assert rf_entry is not None

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kaku ID 123456 CH 1",
        data={
            CONF_TRANSMITTER: "radio_frequency.test_rf_transmitter",
            CONF_DEVICE_ID: 123456,
            CONF_CHANNEL: 1,
            CONF_GROUP: True,
            CONF_DIM: False,
        },
        unique_id=f"{rf_entry.id}_123456_1_1",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert _kaku_button_entity_ids(hass) == []