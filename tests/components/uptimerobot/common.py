"""Common constants and functions for UptimeRobot tests."""

from __future__ import annotations

from enum import Enum
from typing import Any
from unittest.mock import patch

from pyuptimerobot import (
    APIStatus,
    UptimeRobotAccount,
    UptimeRobotApiError,
    UptimeRobotApiResponse,
    UptimeRobotMonitor,
)

from homeassistant import config_entries
from homeassistant.components.uptimerobot.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_UPTIMEROBOT_API_KEY = "u0242ac120003"
MOCK_UPTIMEROBOT_API_KEY_READ_ONLY = "ur0242ac120003"
MOCK_UPTIMEROBOT_EMAIL = "test@test.test"
MOCK_UPTIMEROBOT_UNIQUE_ID = "1234567890"

MOCK_UPTIMEROBOT_ACCOUNT = {
    "email": MOCK_UPTIMEROBOT_EMAIL,
    "user_id": 1234567890,
    "up_monitors": 1,
}
MOCK_UPTIMEROBOT_ERROR = {"message": "test error from API."}
MOCK_UPTIMEROBOT_MONITOR = {
    "id": 1234,
    "friendly_name": "Test monitor",
    "status": 2,
    "type": 1,
    "url": "http://example.com",
}
MOCK_UPTIMEROBOT_MONITOR_PAUSED = {
    "id": 1234,
    "friendly_name": "Test monitor",
    "status": 0,
    "type": 1,
    "url": "http://example.com",
}


MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA = {
    "domain": DOMAIN,
    "title": MOCK_UPTIMEROBOT_EMAIL,
    "data": {"platform": DOMAIN, "api_key": MOCK_UPTIMEROBOT_API_KEY},
    "unique_id": MOCK_UPTIMEROBOT_UNIQUE_ID,
    "source": config_entries.SOURCE_USER,
}
MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA_KEY_READ_ONLY = {
    "domain": DOMAIN,
    "title": MOCK_UPTIMEROBOT_EMAIL,
    "data": {"platform": DOMAIN, "api_key": MOCK_UPTIMEROBOT_API_KEY_READ_ONLY},
    "unique_id": MOCK_UPTIMEROBOT_UNIQUE_ID,
    "source": config_entries.SOURCE_USER,
}

STATE_UP = "up"

UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY = "binary_sensor.test_monitor"
UPTIMEROBOT_SENSOR_TEST_ENTITY = "sensor.test_monitor"
UPTIMEROBOT_SWITCH_TEST_ENTITY = "switch.test_monitor"


class MockApiResponseKey(str, Enum):
    """Mock API response key."""

    ACCOUNT = "account"
    ERROR = "error"
    MONITORS = "monitors"


def mock_uptimerobot_api_response(
    data: dict[str, Any]
    | None
    | list[UptimeRobotMonitor]
    | UptimeRobotAccount
    | UptimeRobotApiError = None,
    status: APIStatus = APIStatus.OK,
    key: MockApiResponseKey = MockApiResponseKey.MONITORS,
) -> UptimeRobotApiResponse:
    """Mock API response for UptimeRobot."""
    return UptimeRobotApiResponse.from_dict(
        {
            "stat": {"error": APIStatus.FAIL}.get(key, status),
            key: data
            if data is not None
            else {
                "account": MOCK_UPTIMEROBOT_ACCOUNT,
                "error": MOCK_UPTIMEROBOT_ERROR,
                "monitors": [MOCK_UPTIMEROBOT_MONITOR],
            }.get(key, {}),
        }
    )


async def setup_uptimerobot_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the UptimeRobot integration."""
    mock_entry = MockConfigEntry(**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA)
    mock_entry.add_to_hass(hass)

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        return_value=mock_uptimerobot_api_response(data=[MOCK_UPTIMEROBOT_MONITOR]),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY).state == STATE_ON
    assert hass.states.get(UPTIMEROBOT_SENSOR_TEST_ENTITY).state == STATE_UP
    assert mock_entry.state is ConfigEntryState.LOADED

    return mock_entry
