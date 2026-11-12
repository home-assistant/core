"""Tests for the steamist binary sensors."""

from aiosteamist import MODEL_550
import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import (
    MOCK_ASYNC_GET_STATUS_550_INACTIVE,
    MOCK_ASYNC_GET_STATUS_550_SHOWER_ACTIVE,
    MOCK_ASYNC_GET_STATUS_550_STEAM_ACTIVE,
    MOCK_ASYNC_GET_STATUS_ACTIVE,
    MOCK_ASYNC_GET_STATUS_INACTIVE,
    _async_setup_entry_with_status,
)


@pytest.mark.usefixtures("mock_aio_discovery")
async def test_binary_sensor_450(hass: HomeAssistant) -> None:
    """Test binary sensors for model 450."""
    await _async_setup_entry_with_status(hass, MOCK_ASYNC_GET_STATUS_ACTIVE)
    assert hass.states.get("binary_sensor.steam_running").state == STATE_ON
    assert hass.states.get("binary_sensor.shower_running") is None


@pytest.mark.usefixtures("mock_aio_discovery")
async def test_binary_sensor_450_inactive(hass: HomeAssistant) -> None:
    """Test binary sensors for model 450 when inactive."""
    await _async_setup_entry_with_status(hass, MOCK_ASYNC_GET_STATUS_INACTIVE)
    assert hass.states.get("binary_sensor.steam_running").state == STATE_OFF


@pytest.mark.usefixtures("mock_aio_discovery")
async def test_binary_sensor_550_steam(hass: HomeAssistant) -> None:
    """Test binary sensors for model 550 when steam is active."""
    await _async_setup_entry_with_status(
        hass, MOCK_ASYNC_GET_STATUS_550_STEAM_ACTIVE, model=MODEL_550
    )
    assert hass.states.get("binary_sensor.steam_running").state == STATE_ON
    assert hass.states.get("binary_sensor.shower_running").state == STATE_OFF


@pytest.mark.usefixtures("mock_aio_discovery")
async def test_binary_sensor_550_shower(hass: HomeAssistant) -> None:
    """Test binary sensors for model 550 when shower is active."""
    await _async_setup_entry_with_status(
        hass, MOCK_ASYNC_GET_STATUS_550_SHOWER_ACTIVE, model=MODEL_550
    )
    assert hass.states.get("binary_sensor.steam_running").state == STATE_OFF
    assert hass.states.get("binary_sensor.shower_running").state == STATE_ON


@pytest.mark.usefixtures("mock_aio_discovery")
async def test_binary_sensor_550_inactive(hass: HomeAssistant) -> None:
    """Test binary sensors for model 550 when inactive."""
    await _async_setup_entry_with_status(
        hass, MOCK_ASYNC_GET_STATUS_550_INACTIVE, model=MODEL_550
    )
    assert hass.states.get("binary_sensor.steam_running").state == STATE_OFF
    assert hass.states.get("binary_sensor.shower_running").state == STATE_OFF
