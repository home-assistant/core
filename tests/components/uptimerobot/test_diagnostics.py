"""Test UptimeRobot diagnostics."""

import json
from unittest.mock import patch

from pyuptimerobot import UptimeRobotException

from homeassistant.core import HomeAssistant

from .common import (
    MOCK_UPTIMEROBOT_ACCOUNT,
    MOCK_UPTIMEROBOT_API_KEY,
    MOCK_UPTIMEROBOT_EMAIL,
    MockApiResponseKey,
    mock_uptimerobot_api_response,
    setup_uptimerobot_integration,
)

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test config entry diagnostics."""
    entry = await setup_uptimerobot_integration(hass)

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=mock_uptimerobot_api_response(
            key=MockApiResponseKey.ACCOUNT,
            data=MOCK_UPTIMEROBOT_ACCOUNT,
        ),
    ):
        result = await get_diagnostics_for_config_entry(
            hass,
            hass_client,
            entry,
        )

    assert result["account"] == {
        "down_monitors": 0,
        "paused_monitors": 0,
        "up_monitors": 1,
    }

    assert result["monitors"] == [
        {"id": 1234, "interval": 0, "status": 2, "type": "MonitorType.HTTP"}
    ]

    assert list(result.keys()) == ["account", "monitors"]

    result_dump = json.dumps(result)
    assert MOCK_UPTIMEROBOT_EMAIL not in result_dump
    assert MOCK_UPTIMEROBOT_API_KEY not in result_dump


async def test_entry_diagnostics_exception(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test config entry diagnostics with exception."""
    entry = await setup_uptimerobot_integration(hass)

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        side_effect=UptimeRobotException("Test exception"),
    ):
        result = await get_diagnostics_for_config_entry(
            hass,
            hass_client,
            entry,
        )

    assert result["account"] == "Test exception"
