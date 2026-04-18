"""Melissa conftest."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.melissa import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import async_load_json_object_fixture


@pytest.fixture
async def mock_melissa(hass: HomeAssistant):
    """Mock the Melissa API."""
    with patch(
        "homeassistant.components.melissa.AsyncMelissa", autospec=True
    ) as mock_client:
        mock_client.return_value.async_connect = AsyncMock()
        mock_client.return_value.async_fetch_devices.return_value = (
            await async_load_json_object_fixture(hass, "fetch_devices.json", DOMAIN)
        )
        mock_client.return_value.async_status.return_value = (
            await async_load_json_object_fixture(hass, "status.json", DOMAIN)
        )
        mock_client.return_value.async_cur_settings.return_value = (
            await async_load_json_object_fixture(hass, "cur_settings.json", DOMAIN)
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
