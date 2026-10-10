"""Test Remootio config-entry setup and unload."""

from unittest.mock import AsyncMock, patch

from pyremootio import (
    RemootioAuthenticationError,
    RemootioConnectionError,
    RemootioTimeoutError,
)
import pytest

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test connecting the client, then disconnecting on unload."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_remootio_client.listen_auth_failure.assert_called_once()
    mock_remootio_client.connect.assert_awaited_once_with()
    mock_remootio_client.enable_reconnect.assert_called_once()
    assert init_integration.runtime_data is mock_remootio_client

    assert await hass.config_entries.async_unload(init_integration.entry_id)

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    mock_remootio_client.disconnect.assert_awaited()
    mock_remootio_client.listen.return_value.assert_called_once()
    mock_remootio_client.listen_connection.return_value.assert_called_once()
    mock_remootio_client.listen_auth_failure.return_value.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        (RemootioConnectionError("offline"), ConfigEntryState.SETUP_RETRY),
        (RemootioTimeoutError("No SERVER_HELLO"), ConfigEntryState.SETUP_RETRY),
        (RemootioAuthenticationError("invalid keys"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_connect_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_remootio_client: AsyncMock,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Test a failed one-shot connect retries or starts reauth."""
    mock_config_entry.add_to_hass(hass)
    mock_remootio_client.connect.side_effect = side_effect

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state
    mock_remootio_client.connect.assert_awaited_once_with()
    mock_remootio_client.enable_reconnect.assert_not_called()
    mock_remootio_client.disconnect.assert_awaited_once()
    if state is ConfigEntryState.SETUP_ERROR:
        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 1
        assert flows[0]["context"]["source"] == SOURCE_REAUTH
        assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_setup_invalid_hex_keys(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test invalid hex keys in the entry fail setup as auth failed."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.remootio.RemootioClient",
        side_effect=ValueError("secret_key must be a 64-character hex string"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test listen_auth_failure starts a reauth flow."""
    on_auth_failure = mock_remootio_client.listen_auth_failure.call_args[0][0]
    on_auth_failure()
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == init_integration.entry_id
    assert flows[0]["step_id"] == "reauth_confirm"
