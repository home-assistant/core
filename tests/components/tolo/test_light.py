"""Tests for the TOLO Sauna light platform."""

from unittest.mock import MagicMock

import pytest
from tololib import Calefaction, Model, ToloStatus

from homeassistant.components.light import (
    ATTR_COLOR_MODE,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

LIGHT_ENTITY_ID = "light.tolo_sauna_light"


@pytest.mark.usefixtures("init_integration")
async def test_light_state_on(
    hass: HomeAssistant,
) -> None:
    """Test the light entity state when on."""
    state = hass.states.get(LIGHT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.ONOFF
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]


@pytest.mark.usefixtures("init_integration")
async def test_light_turn_on(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test turning on the light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.set_lamp_on.assert_called_once_with(True)


@pytest.mark.usefixtures("init_integration")
async def test_light_turn_off(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test turning off the light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.set_lamp_on.assert_called_once_with(False)


async def test_light_off_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test light state when off."""
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

    state = hass.states.get(LIGHT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
