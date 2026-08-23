"""Test the IDrive e2 storage integration."""

from unittest.mock import AsyncMock, patch

from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    ParamValidationError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry_does_not_mask_when_close_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test close failures do not mask the original setup exception."""
    mock_config_entry.add_to_hass(hass)

    # Force setup to fail after the client has been created
    mock_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadBucket"
    )

    # Also force close() to fail
    mock_client.close.side_effect = RuntimeError("boom")

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    mock_client.close.assert_awaited_once()


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (
            ParamValidationError(report="Invalid bucket name"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (ValueError(), ConfigEntryState.SETUP_ERROR),
        (
            EndpointConnectionError(endpoint_url="https://example.com"),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_create_client_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test various setup errors."""
    with patch(
        "homeassistant.components.idrive_e2.AioSession.create_client",
        side_effect=exception,
    ):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is state


@pytest.mark.parametrize(
    ("error_response"),
    [
        {"Error": {"Code": "InvalidAccessKeyId"}},
        {"Error": {"Code": "404", "Message": "Not Found"}},
    ],
    ids=["invalid_access_key", "bucket_not_found"],
)
async def test_setup_entry_head_bucket_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    error_response: dict,
) -> None:
    """Test setup_entry errors when calling head_bucket."""
    mock_client.head_bucket.side_effect = ClientError(
        error_response=error_response,
        operation_name="head_bucket",
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
