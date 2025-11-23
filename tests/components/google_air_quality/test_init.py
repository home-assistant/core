"""Tests for Google Air Quality."""

from unittest.mock import AsyncMock

from google_air_quality_api.exceptions import GoogleAirQualityApiError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test successful setup and unload."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "failing_api_method",
    [
        "async_air_quality",
    ],
)
async def test_config_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    failing_api_method: str,
) -> None:
    """Test for setup failure if an API call fails."""
    getattr(mock_api, failing_api_method).side_effect = GoogleAirQualityApiError()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
