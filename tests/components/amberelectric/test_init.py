"""Tests for the Amber Electric integration setup and teardown."""

from unittest.mock import AsyncMock, Mock, patch

from amberelectric import ApiException
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import MOCK_API_TOKEN, create_amber_config_entry
from .helpers import GENERAL_CHANNEL, GENERAL_ONLY_SITE_ID


@pytest.fixture
def config_entry(hass: HomeAssistant) -> Mock:
    """Return a config entry pre-added to hass."""
    entry = create_amber_config_entry(GENERAL_ONLY_SITE_ID, GENERAL_ONLY_SITE_ID, "home")
    entry.add_to_hass(hass)
    return entry


async def test_api_client_closed_on_first_refresh_failure(
    hass: HomeAssistant, config_entry: Mock
) -> None:
    """Test that the ApiClient is closed when the first refresh fails."""
    mock_api_client = Mock()
    mock_api_instance = Mock()
    mock_api_instance.get_current_prices.side_effect = ApiException(status=500)

    with (
        patch(
            "homeassistant.components.amberelectric.amberelectric.ApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "homeassistant.components.amberelectric.amberelectric.AmberApi",
            return_value=mock_api_instance,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_api_client.close.assert_called_once()


async def test_api_client_closed_on_forward_entry_setups_failure(
    hass: HomeAssistant, config_entry: Mock
) -> None:
    """Test that the ApiClient is closed when async_forward_entry_setups fails."""
    mock_api_client = Mock()
    mock_api_instance = Mock()
    mock_api_instance.get_current_prices.return_value = GENERAL_CHANNEL

    with (
        patch(
            "homeassistant.components.amberelectric.amberelectric.ApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "homeassistant.components.amberelectric.amberelectric.AmberApi",
            return_value=mock_api_instance,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            side_effect=RuntimeError("platform setup failed"),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    mock_api_client.close.assert_called_once()


async def test_api_client_closed_on_unload(
    hass: HomeAssistant, config_entry: Mock
) -> None:
    """Test that the ApiClient is closed on normal entry unload."""
    mock_api_client = Mock()
    mock_api_instance = Mock()
    mock_api_instance.get_current_prices.return_value = GENERAL_CHANNEL

    with (
        patch(
            "homeassistant.components.amberelectric.amberelectric.ApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "homeassistant.components.amberelectric.amberelectric.AmberApi",
            return_value=mock_api_instance,
        ),
    ):
        await setup_integration(hass, config_entry)
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    mock_api_client.close.assert_called_once()
