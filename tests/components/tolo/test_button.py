"""Tests for the TOLO Sauna button platform."""

from unittest.mock import MagicMock

import pytest
from tololib import (
    AromaTherapySlot,
    Calefaction,
    LampMode,
    Model,
    ToloSettings,
    ToloStatus,
)

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

BUTTON_ENTITY_ID = "button.tolo_sauna"


@pytest.mark.usefixtures("init_integration")
async def test_lamp_next_color_button(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test pressing the lamp next color button."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: BUTTON_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.lamp_change_color.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_lamp_next_color_button_available_when_lamp_on_manual(
    hass: HomeAssistant,
) -> None:
    """Test button is available when lamp is on and mode is manual."""
    state = hass.states.get(BUTTON_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_lamp_next_color_button_unavailable_when_lamp_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test button is unavailable when lamp is off."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=True,
        current_temperature=45,
        power_timer=10,
        flow_in=True,
        flow_out=False,
        calefaction=Calefaction.HEAT,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=False,
        water_level=2,
        fan_on=True,
        fan_timer=5,
        current_humidity=70,
        tank_temperature=50,
        model=Model.DOMESTIC,
        salt_bath_on=False,
        salt_bath_timer=None,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(BUTTON_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_lamp_next_color_button_unavailable_when_automatic_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test button is unavailable when lamp mode is automatic."""
    mock_tolo_client.get_settings.return_value = ToloSettings(
        target_temperature=50,
        power_timer=30,
        aroma_therapy_slot=AromaTherapySlot.A,
        sweep_timer=None,
        fan_timer=20,
        target_humidity=80,
        salt_bath_timer=25,
        lamp_mode=LampMode.AUTOMATIC,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(BUTTON_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
