"""Test the S3 API."""

import botocore
import pytest

from homeassistant.components.s3.api import (
    CannotConnectError,
    InvalidBucketNameError,
    InvalidCredentialsError,
    InvalidEndpointURLError,
    get_client,
)
from homeassistant.components.s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
)


@pytest.fixture
def user_input():
    """Fixture for S3 data."""
    return {
        CONF_ENDPOINT_URL: "https://s3.amazonaws.com",
        CONF_SECRET_ACCESS_KEY: "test_secret",
        CONF_ACCESS_KEY_ID: "test_key",
        CONF_BUCKET: "test_bucket",
    }


async def test_get_client_success(user_input) -> None:
    """Test successful client creation."""
    async with get_client(user_input) as client:
        client.head_bucket.assert_called_once_with(Bucket=user_input[CONF_BUCKET])


async def test_get_client_invalid_endpoint_url(user_input, mock_client) -> None:
    """Test invalid endpoint URL."""
    user_input[CONF_ENDPOINT_URL] = "invalid_url"
    mock_client.__aenter__.side_effect = ValueError

    with pytest.raises(InvalidEndpointURLError):
        async with get_client(user_input):
            pass


@pytest.mark.parametrize(
    ("side_effect", "expected_exception"),
    [
        (
            botocore.exceptions.EndpointConnectionError(
                endpoint_url="https://s3.amazonaws.com"
            ),
            CannotConnectError,
        ),
        (
            botocore.exceptions.ClientError(
                error_response={"Error": {"Code": "InvalidAccessKeyId"}},
                operation_name="head_bucket",
            ),
            InvalidCredentialsError,
        ),
    ],
)
async def test_get_client_errors(
    user_input, mock_client, side_effect, expected_exception
) -> None:
    """Test various client connection errors."""
    mock_client.head_bucket.side_effect = side_effect

    with pytest.raises(expected_exception):
        async with get_client(user_input):
            pass


async def test_get_client_invalid_bucket_name(user_input, mock_client) -> None:
    """Test invalid bucket name."""
    mock_client.__aenter__.side_effect = botocore.exceptions.ParamValidationError(
        report="Invalid bucket name"
    )

    with pytest.raises(InvalidBucketNameError):
        async with get_client(user_input):
            pass
