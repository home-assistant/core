"""Tests for Google Air Quality."""

from google_air_quality_api.exceptions import GoogleAirQualityApiError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_integration")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload."""
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("setup_integration_and_subentry")
@pytest.mark.parametrize("api_error", [GoogleAirQualityApiError("some error")])
async def test_async_update_data_failure(
    hass: HomeAssistant,
    config_and_subentry: MockConfigEntry,
) -> None:
    """Test for no reply from the API."""
    assert config_and_subentry.state is ConfigEntryState.SETUP_RETRY
