"""Common constants and functions for UptimeRobot tests."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from unittest.mock import patch

from pyuptimerobot import API_PATH_MONITORS, UptimeRobotApiResponse

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
    "monitorsCount": 1,
}
MOCK_UPTIMEROBOT_ERROR = {"message": "test error from API."}
MOCK_UPTIMEROBOT_MONITOR = {
    "id": 1234,
    "friendlyName": "Test monitor",
    "interval": 300,
    "status": "UP",
    "type": "HTTP",
    "url": "http://example.com",
}
MOCK_UPTIMEROBOT_MONITOR_PAUSED = {
    "id": 1234,
    "friendlyName": "Test monitor",
    "interval": 300,
    "status": "PAUSED",
    "type": "HTTP",
    "url": "http://example.com",
}
MOCK_UPTIMEROBOT_MONITOR_2 = {
    "id": 5678,
    "friendlyName": "Test monitor 2",
    "interval": 300,
    "status": "UP",
    "type": "HTTP",
    "url": "http://example2.com",
}

MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA = {
    "domain": DOMAIN,
    "title": MOCK_UPTIMEROBOT_EMAIL,
    "data": {"platform": DOMAIN, "api_key": MOCK_UPTIMEROBOT_API_KEY},
    "unique_id": MOCK_UPTIMEROBOT_EMAIL,
    "source": config_entries.SOURCE_USER,
}
MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA_KEY_READ_ONLY = {
    "domain": DOMAIN,
    "title": MOCK_UPTIMEROBOT_EMAIL,
    "data": {"platform": DOMAIN, "api_key": MOCK_UPTIMEROBOT_API_KEY_READ_ONLY},
    "unique_id": MOCK_UPTIMEROBOT_EMAIL,
    "source": config_entries.SOURCE_USER,
}

STATE_UP = "up"

UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY = "binary_sensor.test_monitor"
UPTIMEROBOT_SENSOR_TEST_ENTITY = "sensor.test_monitor"
UPTIMEROBOT_SWITCH_TEST_ENTITY = "switch.test_monitor"


class MockApiResponseKey(StrEnum):
    """Mock API response key."""

    ACCOUNT = "account"
    ERROR = "error"
    MONITORS = "monitors"


def mock_uptimerobot_api_response(
    data: list[dict[str, Any]] | dict[str, Any],
    api_path: str = API_PATH_MONITORS,
) -> UptimeRobotApiResponse:
    """Mock API response for UptimeRobot."""

    if api_path == API_PATH_MONITORS:
        data_dict = {"data": data}
    elif isinstance(data, dict):
        data_dict = data

    return UptimeRobotApiResponse.from_dict(
        {
            "_method": "GET",
            "_api_path": api_path,
            **data_dict,
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

    assert (entity := hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY))
    assert entity.state == STATE_ON
    assert (entity := hass.states.get(UPTIMEROBOT_SENSOR_TEST_ENTITY))
    assert entity.state == STATE_UP
    assert mock_entry.state is ConfigEntryState.LOADED

    return mock_entry
