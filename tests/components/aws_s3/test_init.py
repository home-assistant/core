"""Test the AWS S3 storage integration."""

from unittest.mock import AsyncMock, patch

from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    ParamValidationError,
)
import pytest

from homeassistant.components.aws_s3.backup import S3BackupAgent
from homeassistant.components.aws_s3.const import CONF_BUCKET, CONF_PREFIX, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import USER_INPUT

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


async def test_backward_compatibility_config_entry_without_prefix(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test that old config entries without prefix field load successfully."""

    # Create config entry without prefix (simulating old config)
    old_config_data = {k: v for k, v in USER_INPUT.items() if k != CONF_PREFIX}

    mock_config_entry = MockConfigEntry(
        entry_id="test-old-config",
        title="Old S3 Config",
        domain=DOMAIN,
        data=old_config_data,  # No CONF_PREFIX key
    )

    # Should load successfully without errors
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify the runtime data is set up correctly
    assert mock_config_entry.runtime_data is not None

    # Test that backup agent can be created with old config
    agent = S3BackupAgent(hass, mock_config_entry)

    # Should default to empty prefix
    assert agent._prefix == ""
    assert agent._bucket == old_config_data[CONF_BUCKET]


async def test_config_entry_with_prefix_loads_correctly(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that new config entries with prefix field load successfully."""

    # Should load successfully
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Test that backup agent uses the prefix correctly
    agent = S3BackupAgent(hass, mock_config_entry)

    # Should use the prefix from config
    expected_prefix = mock_config_entry.data[CONF_PREFIX]
    assert agent._prefix == expected_prefix
