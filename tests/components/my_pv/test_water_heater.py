"""Test the my-PV water heater."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TEMPERATURE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_TEMPERATURE,
    STATE_ELECTRIC,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_my_pv_connection")
async def test_water_heater(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of a water heater."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_ELECTRIC
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 54.3
    assert state.attributes[ATTR_MAX_TEMP] == 95
    assert state.attributes[ATTR_MIN_TEMP] == 5
    assert state.attributes[ATTR_TEMPERATURE] == 62.1


@pytest.mark.usefixtures("mock_my_pv_connection")
async def test_water_heater_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_connection: AsyncMock,
) -> None:
    """Test turning the water heater off."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_my_pv_connection.fetch_data.return_value = {
        "temp1": 543,
        "devmode": True,
    }

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_my_pv_connection")
async def test_water_heater_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_connection: AsyncMock,
) -> None:
    """Test turning the water heater on."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_my_pv_connection.fetch_data.return_value = {
        "temp1": 543,
        "devmode": False,
    }

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_ELECTRIC


@pytest.mark.usefixtures("mock_my_pv_connection")
async def test_water_heater_set_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the target temperature."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
            ATTR_TEMPERATURE: 35,
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.attributes[ATTR_TEMPERATURE] == 35
