"""Tests for the Tank Utility sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from homeassistant.components.tank_utility.sensor import SENSOR_ATTRS
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed

MOCK_DEVICE_ID = "device_1"

CONFIG = {
    "sensor": {
        "platform": "tank_utility",
        "email": "test@example.com",
        "password": "test_password",
        "devices": [MOCK_DEVICE_ID],
    }
}

DEVICE_DATA = {
    "name": "My Propane Tank",
    "address": "123 Main St",
    "capacity": 500,
    "fuelType": "propane",
    "orientation": "horizontal",
    "status": "ok",
    "lastReading": {
        "tank": 78.43,
        "time": 1600000000,
        "time_iso": "2020-09-13T12:00:00Z",
    },
}


@pytest.fixture
def mock_get_token() -> MagicMock:
    """Mock auth.get_token."""
    with patch(
        "homeassistant.components.tank_utility.sensor.auth.get_token",
        return_value="mock_token",
    ) as mock:
        yield mock


@pytest.fixture
def mock_get_device_data() -> MagicMock:
    """Mock tank_monitor.get_device_data."""
    with patch(
        "homeassistant.components.tank_utility.sensor.tank_monitor.get_device_data",
        return_value=dict(DEVICE_DATA),
    ) as mock:
        yield mock


async def test_setup_platform_success(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
    mock_get_device_data: MagicMock,
) -> None:
    """Test successful setup of Tank Utility sensor."""
    assert await async_setup_component(hass, "sensor", CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is not None
    assert state.state == "78.4"
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    for attr in SENSOR_ATTRS:
        assert attr in state.attributes


async def test_setup_platform_unauthorized(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
) -> None:
    """Test setup with invalid credentials (401 error)."""
    response = requests.Response()
    response.status_code = requests.codes.unauthorized
    mock_get_token.side_effect = requests.exceptions.HTTPError(response=response)

    assert await async_setup_component(hass, "sensor", CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is None


async def test_setup_platform_other_http_error(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
) -> None:
    """Test setup with another HTTP error fails cleanly."""
    response = requests.Response()
    response.status_code = requests.codes.internal_server_error
    mock_get_token.side_effect = requests.exceptions.HTTPError(response=response)

    assert await async_setup_component(hass, "sensor", CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is None


async def test_sensor_update_token_refresh(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
    mock_get_device_data: MagicMock,
) -> None:
    """Test token refresh on 401 during sensor update."""
    assert await async_setup_component(hass, "sensor", CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is not None
    assert state.state == "78.4"

    unauthorized_response = requests.Response()
    unauthorized_response.status_code = requests.codes.unauthorized

    updated_data = dict(DEVICE_DATA)
    updated_data["lastReading"] = dict(DEVICE_DATA["lastReading"])
    updated_data["lastReading"]["tank"] = 65.2

    mock_get_device_data.side_effect = [
        requests.exceptions.HTTPError(response=unauthorized_response),
        updated_data,
    ]

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is not None
    assert state.state == "65.2"
    mock_get_token.assert_called_with("test@example.com", "test_password", force=True)
