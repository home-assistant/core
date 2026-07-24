"""Tests for the TOLO Sauna fan platform."""

from unittest.mock import MagicMock

import pytest
from tololib import Calefaction, Model, ToloStatus

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FAN_ENTITY_ID = "fan.tolo_sauna_fan"


@pytest.mark.usefixtures("init_integration")
async def test_fan_state(
    hass: HomeAssistant,
) -> None:
    """Test the fan entity state."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_fan_turn_on(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test turning on the fan."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.set_fan_on.assert_called_once_with(True)


@pytest.mark.usefixtures("init_integration")
async def test_fan_turn_off(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test turning off the fan."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.set_fan_on.assert_called_once_with(False)


async def test_fan_off_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test fan state when off."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=False,
        current_temperature=30,
        power_timer=None,
        flow_in=False,
        flow_out=False,
        calefaction=Calefaction.INACTIVE,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=False,
        water_level=0,
        fan_on=False,
        fan_timer=None,
        current_humidity=50,
        tank_temperature=30,
        model=Model.DOMESTIC,
        salt_bath_on=False,
        salt_bath_timer=None,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(FAN_ENTITY_ID)
    assert state is not None
    assert state.state == "off"
