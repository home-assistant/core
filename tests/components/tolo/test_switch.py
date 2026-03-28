"""Tests for the TOLO Sauna switch platform."""

from unittest.mock import MagicMock

import pytest
from tololib import Calefaction, Model, ToloStatus

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

AROMA_THERAPY_ENTITY_ID = "switch.tolo_sauna_aroma_therapy"
SALT_BATH_ENTITY_ID = "switch.tolo_sauna_salt_bath"


@pytest.mark.usefixtures("init_integration")
async def test_aroma_therapy_switch_on(
    hass: HomeAssistant,
) -> None:
    """Test aroma therapy switch is on."""
    state = hass.states.get(AROMA_THERAPY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_salt_bath_switch_on(
    hass: HomeAssistant,
) -> None:
    """Test salt bath switch is on."""
    state = hass.states.get(SALT_BATH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_aroma_therapy_turn_on(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test turning on aroma therapy."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: AROMA_THERAPY_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.set_aroma_therapy_on.assert_called_once_with(True)


@pytest.mark.usefixtures("init_integration")
async def test_aroma_therapy_turn_off(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test turning off aroma therapy."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: AROMA_THERAPY_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.set_aroma_therapy_on.assert_called_once_with(False)


@pytest.mark.usefixtures("init_integration")
async def test_salt_bath_turn_on(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test turning on salt bath."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SALT_BATH_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.set_salt_bath_on.assert_called_once_with(True)


@pytest.mark.usefixtures("init_integration")
async def test_salt_bath_turn_off(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test turning off salt bath."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SALT_BATH_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.set_salt_bath_on.assert_called_once_with(False)


async def test_switches_off_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test switches report off when features are disabled."""
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

    state = hass.states.get(AROMA_THERAPY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    state = hass.states.get(SALT_BATH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
