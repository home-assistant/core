"""Test the Tessie sensor platform."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.tessie.coordinator import TESSIE_SYNC_INTERVAL
from homeassistant.components.tessie.sensor import TessieStatus
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .common import (
    ERROR_AUTH,
    ERROR_CONNECTION,
    ERROR_TIMEOUT,
    ERROR_UNKNOWN,
    TEST_VEHICLE_STATE_ASLEEP,
    TEST_VEHICLE_STATE_ONLINE,
    setup_platform,
)

from tests.common import async_fire_time_changed

WAIT = timedelta(seconds=TESSIE_SYNC_INTERVAL)


@pytest.fixture
def mock_get_state():
    """Mock get_state function."""
    with patch(
        "homeassistant.components.tessie.coordinator.get_state",
    ) as mock_get_state:
        yield mock_get_state


async def test_coordinator_online(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles online vehciles."""

    mock_get_state.return_value = TEST_VEHICLE_STATE_ONLINE
    await setup_platform(hass)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("sensor.test_status").state == TessieStatus.ONLINE


async def test_coordinator_asleep(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles asleep vehicles."""

    mock_get_state.return_value = TEST_VEHICLE_STATE_ASLEEP
    await setup_platform(hass)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("sensor.test_status").state == TessieStatus.ASLEEP


async def test_coordinator_clienterror(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles client errors."""

    mock_get_state.side_effect = ERROR_UNKNOWN
    await setup_platform(hass)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("sensor.test_status").state == STATE_UNAVAILABLE


async def test_coordinator_timeout(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles timeout errors."""

    mock_get_state.side_effect = ERROR_TIMEOUT
    await setup_platform(hass)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("sensor.test_status").state == TessieStatus.OFFLINE


async def test_coordinator_auth(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles timeout errors."""

    mock_get_state.side_effect = ERROR_AUTH
    await setup_platform(hass)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()


async def test_coordinator_connection(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles connection errors."""

    mock_get_state.side_effect = ERROR_CONNECTION
    await setup_platform(hass)
    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("sensor.test_status").state == STATE_UNAVAILABLE
