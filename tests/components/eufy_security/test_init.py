"""Test the Eufy Security integration setup."""

from unittest.mock import MagicMock, patch

from homeassistant.components.eufy_security.api import (
    CannotConnectError,
    EufySecurityError,
    InvalidCredentialsError,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eufy_api: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails with invalid credentials."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = MagicMock(
            side_effect=InvalidCredentialsError("Invalid credentials")
        )
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries on connection error."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = MagicMock(
            side_effect=CannotConnectError("Connection failed")
        )
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries on generic API error."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = MagicMock(side_effect=EufySecurityError("API error"))
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test successful unload of a config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
