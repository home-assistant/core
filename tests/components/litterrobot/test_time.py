"""Test the Litter-Robot time entity."""

from __future__ import annotations

from datetime import datetime, time
from unittest.mock import MagicMock

from pylitterbot import LitterRobot3
import pytest

from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import setup_integration

SLEEP_START_TIME_ENTITY_ID = "time.test_sleep_mode_start_time"


@pytest.mark.freeze_time(datetime(2023, 7, 1, 12))
async def test_sleep_mode_start_time(
    hass: HomeAssistant, mock_account: MagicMock
) -> None:
    """Tests the sleep mode start time."""
    await setup_integration(hass, mock_account, TIME_DOMAIN)

    entity = hass.states.get(SLEEP_START_TIME_ENTITY_ID)
    assert entity
    assert entity.state == "17:16:00"

    robot: LitterRobot3 = mock_account.robots[0]
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: SLEEP_START_TIME_ENTITY_ID, ATTR_TIME: time(23, 0)},
        blocking=True,
    )
    robot.set_sleep_mode.assert_awaited_once_with(True, time(23, 0))


async def test_time_command_exception(
    hass: HomeAssistant, mock_account_with_side_effects: MagicMock
) -> None:
    """Test that LitterRobotException is wrapped in HomeAssistantError."""
    await setup_integration(hass, mock_account_with_side_effects, TIME_DOMAIN)

    with pytest.raises(HomeAssistantError, match="Invalid command: oops"):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: SLEEP_START_TIME_ENTITY_ID, ATTR_TIME: time(23, 0)},
            blocking=True,
        )
