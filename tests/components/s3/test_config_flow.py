"""Test the S3 config flow."""

from unittest.mock import AsyncMock, patch

from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    ParamValidationError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.s3.config_flow import _detect_checksum_mode
from homeassistant.components.s3.const import (
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    DOMAIN,
    ChecksumMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import EXPECTED_CONFIG_FLOW_DATA, USER_INPUT

from tests.common import MockConfigEntry


async def _async_start_flow(
    hass: HomeAssistant,
) -> FlowResultType:
    """Initialize the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )


async def test_flow(hass: HomeAssistant) -> None:
    """Test config flow."""
    result = await _async_start_flow(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == EXPECTED_CONFIG_FLOW_DATA


@pytest.mark.parametrize(
    ("exception", "errors"),
    [
        (
            ParamValidationError(report="Invalid bucket name"),
            {CONF_BUCKET: "invalid_bucket_name"},
        ),
        (ValueError(), {CONF_ENDPOINT_URL: "invalid_endpoint_url"}),
        (
            EndpointConnectionError(endpoint_url="http://example.com"),
            {CONF_ENDPOINT_URL: "cannot_connect"},
        ),
    ],
)
async def test_flow_create_client_errors(
    hass: HomeAssistant,
    exception: Exception,
    errors: dict[str, str],
) -> None:
    """Test config flow errors."""
    with patch(
        "aiobotocore.session.AioSession.create_client",
        side_effect=exception,
    ):
        result = await _async_start_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    # Fix and finish the test
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == EXPECTED_CONFIG_FLOW_DATA


async def test_flow_head_bucket_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test setup_entry error when calling head_bucket."""
    mock_client.head_bucket.side_effect = ClientError(
        error_response={"Error": {"Code": "InvalidAccessKeyId"}},
        operation_name="head_bucket",
    )
    result = await _async_start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_credentials"}

    # Fix and finish the test
    mock_client.head_bucket.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == EXPECTED_CONFIG_FLOW_DATA


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if the account is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await _async_start_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error_response", "expected_checksum_mode"),
    [
        (
            {
                "Error": {
                    "Message": "Unsupported header 'x-amz-sdk-checksum-algorithm'",
                    "Code": "",
                }
            },
            ChecksumMode.WHEN_REQUIRED,
        ),
        (
            {
                "Error": {
                    "Message": "",
                    "Code": "XAmzContentSHA256Mismatch",
                }
            },
            ChecksumMode.WHEN_REQUIRED,
        ),
        (None, ChecksumMode.WHEN_SUPPORTED),
    ],
)
async def test_detect_checksum_mode(
    mock_client: AsyncMock, error_response, expected_checksum_mode
) -> None:
    """Test detection of checksum modes."""

    if error_response:
        mock_client.put_object.side_effect = ClientError(
            error_response=error_response,
            operation_name="put_object",
        )

    checksum_mode = await _detect_checksum_mode(mock_client, "test-bucket")
    assert checksum_mode == expected_checksum_mode


async def test_detect_checksum_mode_raises(mock_client: AsyncMock) -> None:
    """Test other failure during detection of checksum modes."""
    mock_client.put_object.side_effect = ClientError(
        error_response={"Error": {"Message": "Unknown error", "Code": ""}},
        operation_name="put_object",
    )

    with pytest.raises(ClientError):
        await _detect_checksum_mode(mock_client, "test-bucket")
