"""Tests for the Atomberg fan platform."""

from unittest.mock import AsyncMock, call

from atomberg_api import AtombergConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

ON_FAN = "fan.living_room"
OFF_FAN = "fan.bedroom"
ON_ID = "a4cf12abcdef"
OFF_ID = "a4cf12123456"


@pytest.mark.usefixtures("mock_client")
async def test_state(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test initial fan state maps speed 3 of 6 to 50 percent."""
    await setup_integration(hass, mock_config_entry)

    on = hass.states.get(ON_FAN)
    assert on.state == STATE_ON
    assert on.attributes[ATTR_PERCENTAGE] == 50
    assert hass.states.get(OFF_FAN).state == STATE_OFF


async def test_turn_off(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning off sends the power command and updates state."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ON_FAN}, blocking=True
    )

    mock_client.async_send_command.assert_awaited_once_with(ON_ID, {"power": False})
    assert hass.states.get(ON_FAN).state == STATE_OFF


async def test_turn_on_powers_on_only(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning on without a speed sends one command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: OFF_FAN}, blocking=True
    )

    mock_client.async_send_command.assert_awaited_once_with(OFF_ID, {"power": True})
    assert hass.states.get(OFF_FAN).state == STATE_ON


@pytest.mark.parametrize(("percentage", "speed"), [(16, 1), (50, 3), (100, 6)])
async def test_set_percentage_when_on(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    percentage: int,
    speed: int,
) -> None:
    """Test changing speed on a running fan sends only the speed."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ON_FAN, ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    mock_client.async_send_command.assert_awaited_once_with(ON_ID, {"speed": speed})


async def test_set_percentage_when_off_powers_on_first(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a speed change on an off fan powers it on, then sets the speed."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: OFF_FAN, ATTR_PERCENTAGE: 100},
        blocking=True,
    )

    assert mock_client.async_send_command.await_args_list == [
        call(OFF_ID, {"power": True}),
        call(OFF_ID, {"speed": 6}),
    ]


async def test_set_percentage_zero_turns_off(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test 0 percent turns the fan off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ON_FAN, ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    mock_client.async_send_command.assert_awaited_once_with(ON_ID, {"power": False})


async def test_command_error(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test API errors surface as Home Assistant errors and leave state unchanged."""
    await setup_integration(hass, mock_config_entry)
    mock_client.async_send_command.side_effect = AtombergConnectionError("boom")

    with pytest.raises(HomeAssistantError, match="boom"):
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ON_FAN}, blocking=True
        )

    assert hass.states.get(ON_FAN).state == STATE_ON
