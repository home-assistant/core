"""Melissa conftest."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.common import load_json_object_fixture


@pytest.fixture
async def mock_melissa():
    """Mock the Melissa API."""
    with patch(
        "homeassistant.components.melissa.AsyncMelissa", autospec=True
    ) as mock_client:
        mock_client.return_value.async_connect = AsyncMock()
        mock_client.return_value.async_fetch_devices.return_value = (
            load_json_object_fixture("fetch_devices.json", "melissa")
        )
        mock_client.return_value.async_status.return_value = load_json_object_fixture(
            "status.json", "melissa"
        )
        mock_client.return_value.async_cur_settings.return_value = (
            load_json_object_fixture("cur_settings.json", "melissa")
        )

        mock_client.return_value.STATE_OFF = 0
        mock_client.return_value.STATE_ON = 1
        mock_client.return_value.STATE_IDLE = 2

        mock_client.return_value.MODE_AUTO = 0
        mock_client.return_value.MODE_FAN = 1
        mock_client.return_value.MODE_HEAT = 2
        mock_client.return_value.MODE_COOL = 3
        mock_client.return_value.MODE_DRY = 4

        mock_client.return_value.FAN_AUTO = 0
        mock_client.return_value.FAN_LOW = 1
        mock_client.return_value.FAN_MEDIUM = 2
        mock_client.return_value.FAN_HIGH = 3

        mock_client.return_value.STATE = "state"
        mock_client.return_value.MODE = "mode"
        mock_client.return_value.FAN = "fan"
        mock_client.return_value.TEMP = "temp"
        mock_client.return_value.HUMIDITY = "humidity"
        yield mock_client
