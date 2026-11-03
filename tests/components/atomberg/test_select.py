"""Tests for the Atomberg timer select."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import setup_integration

SELECT = "select.living_room_timer"


async def test_initial_state(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test 2 timer hours maps to the 2 hour option."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SELECT).state == "2_hours"


@pytest.mark.parametrize(
    ("option", "command_value"),
    [("off", 0), ("1_hour", 1), ("3_hours", 3), ("6_hours", 4)],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    option: str,
    command_value: int,
) -> None:
    """Test option names map to the API's timer index, where 6 hours is index 4."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT, ATTR_OPTION: option},
        blocking=True,
    )

    mock_client.async_send_command.assert_awaited_once_with(
        "a4cf12abcdef", {"timer": command_value}
    )
    assert hass.states.get(SELECT).state == option
