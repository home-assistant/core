"""Test Flow-it fan platform."""

from unittest.mock import AsyncMock

from flow_it_api.const import Speed
import pytest

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.flow_it.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flow-it Device",
        unique_id="00:11:22:33:44:55",
        data={
            "host": "http://1.1.1.1",
            "username": "api",
            "password": "test-password",
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_fan_turn_on(
    hass: HomeAssistant, mock_flow_it: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning on the fan."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "fan.00_11_22_33_44_55"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_flow_it.return_value.send_command.assert_awaited_once_with(
        Speed.LEVEL_1, flow_in=True, flow_out=True
    )


async def test_fan_turn_off(
    hass: HomeAssistant, mock_flow_it: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning off the fan."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "fan.00_11_22_33_44_55"

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_flow_it.return_value.send_command.assert_awaited_once_with(
        Speed.OFF, flow_in=True, flow_out=True
    )


async def test_fan_set_percentage(
    hass: HomeAssistant, mock_flow_it: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting percentage."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "fan.00_11_22_33_44_55"

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 60},
        blocking=True,
    )
    mock_flow_it.return_value.send_command.assert_awaited_once_with(
        Speed.LEVEL_3, flow_in=True, flow_out=True
    )


async def test_fan_set_percentage_zero(
    hass: HomeAssistant, mock_flow_it: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting percentage to 0 turns off fan."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "fan.00_11_22_33_44_55"

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    mock_flow_it.return_value.send_command.assert_awaited_once_with(
        Speed.OFF, flow_in=True, flow_out=True
    )


async def test_fan_set_preset_mode(
    hass: HomeAssistant, mock_flow_it: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting preset mode."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "fan.00_11_22_33_44_55"

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )
    mock_flow_it.return_value.send_command.assert_awaited_once_with(
        Speed.BOOST, flow_in=True, flow_out=True
    )
