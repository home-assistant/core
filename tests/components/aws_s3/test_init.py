"""Test the AWS S3 storage integration."""

from unittest.mock import AsyncMock, patch

from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    ParamValidationError,
)
import pytest

from homeassistant.components.aws_s3.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import CONFIG_ENTRY_DATA_DEFAULT_CREDENTIALS

from tests.common import MockConfigEntry


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
        "aiobotocore.session.AioSession.create_client",
        side_effect=exception,
    ):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is state


async def test_load_config_entry_with_default_credentials(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test loading an entry that has Boto3 resolve the credentials."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA_DEFAULT_CREDENTIALS)
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_no_credentials_found(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test setup error when Boto3 cannot resolve any credentials."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA_DEFAULT_CREDENTIALS)
    mock_client.head_bucket.side_effect = NoCredentialsError()
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_head_bucket_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test setup_entry error when calling head_bucket."""
    mock_client.head_bucket.side_effect = ClientError(
        error_response={"Error": {"Code": "InvalidAccessKeyId"}},
        operation_name="head_bucket",
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
