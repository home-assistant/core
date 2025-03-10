"""Test the S3 API."""

from unittest.mock import AsyncMock, patch

import botocore
import pytest

from homeassistant.components.s3._api import (
    CannotConnectError,
    InvalidBucketNameError,
    InvalidCredentialsError,
    InvalidEndpointURLError,
    get_client,
)


@pytest.fixture
def user_input():
    """Fixture for S3 data."""
    return {
        "endpoint_url": "https://s3.amazonaws.com",
        "secret_access_key": "test_secret",
        "access_key_id": "test_key",
        "bucket": "test_bucket",
    }


@pytest.fixture(autouse=True)
async def mock_create_client():
    """Mock the AioSession.create_client."""
    with patch(
        "homeassistant.components.s3._api.AioSession.create_client",
        autospec=True,
    ) as create_client:
        client = create_client.return_value
        client.head_bucket = AsyncMock()
        create_client.return_value.__aenter__.return_value = client
        yield client


async def test_get_client_success(user_input) -> None:
    """Test successful client creation."""
    async with get_client(user_input) as client:
        client.head_bucket.assert_called_once_with(Bucket=user_input["bucket"])


async def test_get_client_invalid_endpoint_url(user_input, mock_create_client) -> None:
    """Test invalid endpoint URL."""
    user_input["endpoint_url"] = "invalid_url"
    mock_create_client.__aenter__.side_effect = ValueError

    with pytest.raises(InvalidEndpointURLError):
        async with get_client(user_input):
            pass


async def test_get_client_cannot_connect(user_input, mock_create_client) -> None:
    """Test cannot connect to endpoint."""
    mock_create_client.head_bucket.side_effect = (
        botocore.exceptions.EndpointConnectionError(
            endpoint_url=user_input["endpoint_url"]
        )
    )
    with pytest.raises(CannotConnectError):
        async with get_client(user_input):
            pass


async def test_get_client_invalid_credentials(user_input, mock_create_client) -> None:
    """Test invalid credentials."""
    mock_create_client.head_bucket.side_effect = botocore.exceptions.ClientError(
        error_response={"Error": {"Code": "InvalidAccessKeyId"}},
        operation_name="head_bucket",
    )

    with pytest.raises(InvalidCredentialsError):
        async with get_client(user_input):
            pass


async def test_get_client_invalid_bucket_name(user_input, mock_create_client) -> None:
    """Test invalid bucket name."""
    mock_create_client.__aenter__.side_effect = (
        botocore.exceptions.ParamValidationError(report="Invalid bucket name")
    )

    with pytest.raises(InvalidBucketNameError):
        async with get_client(user_input):
            pass
