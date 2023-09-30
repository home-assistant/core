"""Test the Tami4 component."""
import pytest
from Tami4EdgeAPI import exceptions as APIExceptions

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .conftest import create_config_entry


async def test_init_success(mock_api, hass: HomeAssistant) -> None:
    """Test setup and that we can create the entry."""

    entry = await create_config_entry(hass)
    assert entry.state == config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "mock_get_water_quality", [APIExceptions.APIRequestFailedException], indirect=True
)
async def test_init_with_api_error(mock_api, hass: HomeAssistant) -> None:
    """Test init with api error."""

    entry = await create_config_entry(hass)
    assert entry.state == config_entries.ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "mock__get_devices", [APIExceptions.TokenRefreshFailedException], indirect=True
)
async def test_init_with_token_refresh_error(mock_api, hass: HomeAssistant) -> None:
    """Test init with token refresh error."""

    entry = await create_config_entry(hass)
    assert entry.state == config_entries.ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "mock__get_devices", [APIExceptions.RefreshTokenExpiredException], indirect=True
)
async def test_init_with_token_refresh_expired_error(
    mock_api, hass: HomeAssistant
) -> None:
    """Test init with token refresh expired error."""

    entry = await create_config_entry(hass)
    assert entry.state == config_entries.ConfigEntryState.SETUP_ERROR


async def test_load_unload(mock_api, hass: HomeAssistant) -> None:
    """Config entry can be unloaded."""

    entry = await create_config_entry(hass)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
