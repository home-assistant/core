"""Tests for the Kaku RC button behavior."""

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.kaku_rc.const import (
    CONF_CHANNEL,
    CONF_DEVICE_ID,
    CONF_DIM,
    CONF_GROUP,
    CONF_TRANSMITTER,
    DOMAIN,
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


@pytest.mark.parametrize(
    "group",
    [
        pytest.param(False, id="single_device"),
        pytest.param(True, id="group_device"),
    ],
)
async def test_no_buttons_created(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    group: bool,
) -> None:
    """Test no buttons are created regardless of group setting."""
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
            CONF_GROUP: group,
            CONF_DIM: False,
        },
        unique_id=f"{rf_entry.id}_123456_1_{int(group)}",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert _kaku_button_entity_ids(hass) == []
