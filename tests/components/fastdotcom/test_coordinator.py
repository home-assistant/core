"""Test the FastdotcomDataUpdateCoordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from fastdotcom import (
    FastDotComConnectionError,
    FastDotComError,
    FastDotComTimeoutError,
    FastDotComTokenError,
    FastSpeedtestResult,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.fastdotcom.const import DEFAULT_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import MOCK_DATA


async def test_fastdotcom_data_update_coordinator(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_async_fast_com: AsyncMock,
) -> None:
    """Test the update coordinator."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    session = async_get_clientsession(hass)
    mock_async_fast_com.assert_awaited_once_with(session=session)
    assert not session.closed

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == "100.0"
    assert mock_config_entry.runtime_data.data == MOCK_DATA

    mock_async_fast_com.return_value = FastSpeedtestResult(
        download_speed=250.5,
        upload_speed=120.25,
        unloaded_ping=8.4,
        loaded_ping=12.1,
    )
    freezer.tick(timedelta(hours=DEFAULT_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == "250.5"
    assert mock_async_fast_com.await_count == 2
    assert not session.closed


@pytest.mark.parametrize(
    "error",
    [
        FastDotComConnectionError("connection failed"),
        FastDotComTimeoutError("request timed out"),
        FastDotComTokenError("token discovery failed"),
    ],
)
async def test_fastdotcom_coordinator_error_and_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_async_fast_com: AsyncMock,
    error: FastDotComError,
) -> None:
    """Test coordinator marks entity unavailable on errors and recovers."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == "100.0"

    mock_async_fast_com.side_effect = error
    freezer.tick(timedelta(hours=DEFAULT_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert mock_config_entry.runtime_data.last_update_success is False

    mock_async_fast_com.side_effect = None
    mock_async_fast_com.return_value = FastSpeedtestResult(
        download_speed=75.25,
        upload_speed=30.0,
        unloaded_ping=12.0,
        loaded_ping=18.0,
    )
    freezer.tick(timedelta(hours=DEFAULT_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == "75.25"
    assert mock_config_entry.runtime_data.last_update_success is True
