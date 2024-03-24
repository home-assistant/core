"""Test the Litter-Robot time entity."""

from __future__ import annotations

from datetime import datetime, time
from unittest.mock import MagicMock

from pylitterbot import LitterRobot3
import pytest

from homeassistant.components.time import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

SLEEP_START_TIME_ENTITY_ID = "time.test_sleep_mode_start_time"


@pytest.mark.freeze_time(datetime(2023, 7, 1, 12))
async def test_sleep_mode_start_time(
    hass: HomeAssistant, mock_account: MagicMock
) -> None:
    """Tests the sleep mode start time."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    entity = hass.states.get(SLEEP_START_TIME_ENTITY_ID)
    assert entity
    assert entity.state == "17:16:00"

    robot: LitterRobot3 = mock_account.robots[0]
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        "set_value",
        {ATTR_ENTITY_ID: SLEEP_START_TIME_ENTITY_ID, "time": time(23, 0)},
        blocking=True,
    )
    robot.set_sleep_mode.assert_awaited_once_with(True, time(23, 0))
