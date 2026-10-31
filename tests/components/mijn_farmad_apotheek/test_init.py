"""Test the Mijn Farmad Apotheek integration."""

from unittest.mock import MagicMock

from aiofarmad import FarmadAuthenticationError, FarmadCommunicationError

from homeassistant.components.mijn_farmad_apotheek.const import (
    BASKET_PAGE_SIZE,
    CONF_REFRESH_TOKEN,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from . import API_APB, init_integration


async def test_setup_entry(hass: HomeAssistant, mock_farmad_client: MagicMock) -> None:
    """Test a config entry sets up."""
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    client = mock_farmad_client.return_value
    client.async_get_account.assert_awaited_once()
    client.async_get_baskets.assert_awaited_once_with(
        API_APB, skip=0, take=BASKET_PAGE_SIZE
    )


async def test_setup_entry_not_ready(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test a config entry retries setup when Farmad cannot be reached."""
    mock_farmad_client.return_value.async_get_account.side_effect = (
        FarmadCommunicationError("mock")
    )
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_farmad_client.return_value.async_close.assert_awaited_once()


async def test_setup_entry_auth_failed(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test a config entry starts reauthentication when the session expired."""
    mock_farmad_client.return_value.async_get_account.side_effect = (
        FarmadAuthenticationError("mock")
    )
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    mock_farmad_client.return_value.async_close.assert_awaited_once()
    assert any(entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_setup_entry_not_ready_baskets(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test a config entry retries setup when the order history cannot be read."""
    mock_farmad_client.return_value.async_get_baskets.side_effect = (
        FarmadCommunicationError("mock")
    )
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_farmad_client.return_value.async_close.assert_awaited_once()


async def test_unload_entry(hass: HomeAssistant, mock_farmad_client: MagicMock) -> None:
    """Test a config entry unloads and closes the client."""
    entry = await init_integration(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_farmad_client.return_value.async_close.assert_awaited_once()


async def test_token_rotation(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test rotated tokens are stored and a missing refresh token keeps the old one."""
    entry = await init_integration(hass)
    await mock_farmad_client.call_args.kwargs["on_token_refresh"](
        "new-access-token", "new-refresh-token"
    )
    assert entry.data[CONF_ACCESS_TOKEN] == "new-access-token"
    assert entry.data[CONF_REFRESH_TOKEN] == "new-refresh-token"
    await mock_farmad_client.call_args.kwargs["on_token_refresh"](
        "newer-access-token", None
    )
    assert entry.data[CONF_ACCESS_TOKEN] == "newer-access-token"
    assert entry.data[CONF_REFRESH_TOKEN] == "new-refresh-token"
