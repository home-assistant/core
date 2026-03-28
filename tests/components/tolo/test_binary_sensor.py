"""Tests for the TOLO Sauna binary sensor platform."""

from unittest.mock import MagicMock

import pytest
from tololib import Calefaction, Model, ToloStatus

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

FLOW_IN_ENTITY_ID = "binary_sensor.tolo_sauna"
FLOW_OUT_ENTITY_ID = "binary_sensor.tolo_sauna_2"


@pytest.mark.usefixtures("init_integration")
async def test_flow_in_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the flow in binary sensor reports on when valve is open."""
    entry = entity_registry.async_get(FLOW_IN_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{mock_config_entry.entry_id}_flow_in"

    state = hass.states.get(FLOW_IN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_flow_out_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the flow out binary sensor reports off when valve is closed."""
    entry = entity_registry.async_get(FLOW_OUT_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{mock_config_entry.entry_id}_flow_out"

    state = hass.states.get(FLOW_OUT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_flow_in_off_flow_out_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test flow sensors with reversed state."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=True,
        current_temperature=45,
        power_timer=10,
        flow_in=False,
        flow_out=True,
        calefaction=Calefaction.HEAT,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=True,
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

    state = hass.states.get(FLOW_IN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    state = hass.states.get(FLOW_OUT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
