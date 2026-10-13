"""Test the Cloudflare R2 storage integration."""

from unittest.mock import AsyncMock, patch

from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    ParamValidationError,
)
import pytest

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

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
        (
            ParamValidationError(report="Unknown parameter"),
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


@pytest.mark.parametrize("status_code", [401, 403])
async def test_setup_entry_head_bucket_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    status_code: int,
) -> None:
    """Test rejected credentials start a reauth flow."""
    mock_client.head_bucket.side_effect = ClientError(
        error_response={
            "Error": {"Code": "InvalidAccessKeyId"},
            "ResponseMetadata": {"HTTPStatusCode": status_code},
        },
        operation_name="head_bucket",
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_client.__aexit__.assert_awaited_once()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize("status_code", [429, 500, 503])
async def test_setup_entry_head_bucket_retryable_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    status_code: int,
) -> None:
    """Test transient service errors are retried and do not start reauth."""
    mock_client.head_bucket.side_effect = ClientError(
        error_response={
            "Error": {"Code": str(status_code)},
            "ResponseMetadata": {"HTTPStatusCode": status_code},
        },
        operation_name="head_bucket",
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "service_error"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "error": str(status_code)
    }
    mock_client.__aexit__.assert_awaited_once()
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize("code", ["404", "NoSuchBucket"])
async def test_setup_entry_bucket_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    code: str,
) -> None:
    """Test a missing bucket is a hard error and does not start reauth."""
    mock_client.head_bucket.side_effect = ClientError(
        error_response={"Error": {"Code": code}},
        operation_name="head_bucket",
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "bucket_not_found"
    assert not hass.config_entries.flow.async_progress()


async def test_setup_entry_warms_loader_caches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that create_client passes warm_up_loader_caches config."""
    with patch(
        "homeassistant.components.cloudflare_r2.AioSession.create_client"
    ) as create_client:
        client_ctx = AsyncMock()
        client = AsyncMock()
        client_ctx.__aenter__.return_value = client
        create_client.return_value = client_ctx

        await setup_integration(hass, mock_config_entry)

        create_client.assert_called_once()
        _, kwargs = create_client.call_args
        assert kwargs["config"].warm_up_loader_caches is True
