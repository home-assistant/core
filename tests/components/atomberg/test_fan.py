"""Tests for the Atomberg fan platform."""

from unittest.mock import AsyncMock, call

from atomberg_api import AtombergAuthError, AtombergConnectionError, AtombergError
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


async def test_turn_on_sends_power_even_when_state_is_on(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn on always sends the command, as the cached state may be stale."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ON_FAN).state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ON_FAN}, blocking=True
    )

    mock_client.async_send_command.assert_awaited_once_with(ON_ID, {"power": True})


@pytest.mark.parametrize(("percentage", "speed"), [(16, 1), (50, 3), (100, 6)])
async def test_set_percentage_when_on(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    percentage: int,
    speed: int,
) -> None:
    """Test changing speed always sends the power command first."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ON_FAN, ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    assert mock_client.async_send_command.await_args_list == [
        call(ON_ID, {"power": True}),
        call(ON_ID, {"speed": speed}),
    ]


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


async def test_turn_on_with_percentage_zero_turns_off(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning on at 0 percent turns the fan off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ON_FAN, ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    mock_client.async_send_command.assert_awaited_once_with(ON_ID, {"power": False})


async def test_turn_on_with_percentage(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning on at a speed powers on and sets the speed."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: OFF_FAN, ATTR_PERCENTAGE: 100},
        blocking=True,
    )

    assert mock_client.async_send_command.await_args_list == [
        call(OFF_ID, {"power": True}),
        call(OFF_ID, {"speed": 6}),
    ]


async def test_unknown_speed_has_no_percentage(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a speed outside the known range gives an unknown percentage."""
    mock_client.async_get_states.return_value[ON_ID]["last_recorded_speed"] = 9

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ON_FAN).attributes[ATTR_PERCENTAGE] is None


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (AtombergAuthError, "credentials are invalid"),
        (AtombergError("odd"), "rejected the command: odd"),
    ],
)
async def test_other_command_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception | type[Exception],
    message: str,
) -> None:
    """Test authentication and generic API errors become translated errors."""
    await setup_integration(hass, mock_config_entry)
    mock_client.async_send_command.side_effect = exception

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ON_FAN}, blocking=True
        )


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
