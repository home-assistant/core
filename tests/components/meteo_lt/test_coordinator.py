"""Test Meteo.lt coordinator."""

from unittest.mock import AsyncMock

import aiohttp
import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2025-09-25 10:00:00")
async def test_coordinator_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meteo_lt_api: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator handles connection errors and logs appropriately."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_meteo_lt_api.get_forecast.side_effect = aiohttp.ClientConnectionError(
        "Connection failed"
    )

    coordinator = mock_config_entry.runtime_data

    caplog.clear()
    await coordinator.async_refresh()
    assert "Cannot connect to API for vilnius" in caplog.text

    caplog.clear()
    await coordinator.async_refresh()
    assert "Cannot connect to API for vilnius" not in caplog.text

    state = hass.states.get("weather.vilnius")
    assert state is not None
    assert state.state == "unavailable"

    mock_meteo_lt_api.get_forecast.side_effect = None
    caplog.clear()
    await coordinator.async_refresh()
    assert "API connection restored for vilnius" in caplog.text


@pytest.mark.freeze_time("2025-09-25 10:00:00")
async def test_coordinator_http_error_logging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meteo_lt_api: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator logs HTTP errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_meteo_lt_api.get_forecast.side_effect = aiohttp.ClientResponseError(
        request_info=AsyncMock(),
        history=(),
        status=500,
        message="Internal Server Error",
    )

    coordinator = mock_config_entry.runtime_data

    caplog.clear()
    await coordinator.async_refresh()
    assert "API unavailable for vilnius: HTTP 500" in caplog.text


@pytest.mark.freeze_time("2025-09-25 10:00:00")
async def test_coordinator_client_error_logging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meteo_lt_api: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator logs generic aiohttp.ClientError."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    mock_meteo_lt_api.get_forecast.side_effect = aiohttp.ClientError("Generic error")
    caplog.clear()
    await coordinator.async_refresh()
    assert "Error communicating with API for vilnius" in caplog.text


@pytest.mark.freeze_time("2025-09-25 10:00:00")
async def test_coordinator_timeout_error_logging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meteo_lt_api: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator logs TimeoutError."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    mock_meteo_lt_api.get_forecast.side_effect = TimeoutError("Request timed out")
    caplog.clear()
    await coordinator.async_refresh()
    assert "Error communicating with API for vilnius" in caplog.text
