"""Test the AWS S3 storage integration."""

from itertools import product
from unittest.mock import AsyncMock, patch

from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    ParamValidationError,
    ProfileNotFound,
    TokenRetrievalError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import TEST_INVALID, TEST_PROFILE_NAME

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


_setup_errors = [
    (
        ParamValidationError(report="Invalid bucket name"),
        ConfigEntryState.SETUP_ERROR,
    ),
    (ValueError(), ConfigEntryState.SETUP_ERROR),
    (NoCredentialsError(), ConfigEntryState.SETUP_ERROR),
    (
        ProfileNotFound(profile=TEST_PROFILE_NAME[TEST_INVALID]),
        ConfigEntryState.SETUP_ERROR,
    ),
    (
        TokenRetrievalError(provider="TestProvider", error_msg="Test error"),
        ConfigEntryState.SETUP_ERROR,
    ),
    (
        EndpointConnectionError(endpoint_url="https://example.com"),
        ConfigEntryState.SETUP_RETRY,
    ),
]

_setup_error_locations = [
    "aiobotocore.session.AioSession.__init__",
    "aiobotocore.session.AioSession.create_client",
]


@pytest.mark.parametrize(
    ("exception", "state", "raised_at"),
    [(*p[0], p[1]) for p in product(_setup_errors, _setup_error_locations)],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    state: ConfigEntryState,
    raised_at: str,
) -> None:
    """Test various setup errors."""
    with patch(
        raised_at,
        side_effect=exception,
    ):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is state


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        *_setup_errors,
        (
            ClientError(
                error_response={"Error": {"Code": "InvalidAccessKeyId"}},
                operation_name="head_bucket",
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_setup_entry_head_bucket_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup_entry error when calling head_bucket."""
    mock_client.head_bucket.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state
