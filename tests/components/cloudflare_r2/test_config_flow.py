"""Test the Cloudflare R2 config flow."""

from unittest.mock import AsyncMock, patch

from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    ParamValidationError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.cloudflare_r2.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_PREFIX
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import USER_INPUT

from tests.common import MockConfigEntry


async def _async_start_flow(
    hass: HomeAssistant,
    user_input: dict[str, str] | None = None,
) -> FlowResultType:
    """Initialize the config flow."""
    if user_input is None:
        user_input = USER_INPUT

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )


async def test_flow(hass: HomeAssistant) -> None:
    """Test config flow."""
    create_client = AsyncMock(name="create_client")
    create_client.__aenter__.return_value.head_bucket.return_value = {}

    with patch(
        "homeassistant.components.cloudflare_r2.config_flow.AioSession.create_client",
        return_value=create_client,
    ) as patched_create_client:
        result = await _async_start_flow(hass)

        assert patched_create_client.call_args.kwargs["config"].warm_up_loader_caches

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize(
    ("exception", "errors"),
    [
        (
            ParamValidationError(report="Invalid bucket name"),
            {CONF_BUCKET: "invalid_bucket_name"},
        ),
        (
            ParamValidationError(report="Unknown parameter"),
            {"base": "unknown"},
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
    assert result["data"] == USER_INPUT


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
    assert result["data"] == USER_INPUT


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if the account is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await _async_start_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_create_not_r2_endpoint(
    hass: HomeAssistant,
) -> None:
    """Test config flow with a not R2 endpoint should raise an error."""
    result = await _async_start_flow(
        hass, USER_INPUT | {CONF_ENDPOINT_URL: "http://example.com"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ENDPOINT_URL: "invalid_endpoint_url"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == USER_INPUT


REAUTH_INPUT = {
    CONF_ACCESS_KEY_ID: "NewR2AccessKeyId",
    CONF_SECRET_ACCESS_KEY: "NewR2SecretAccessKey",
}


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication updates the stored credentials."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == USER_INPUT | REAUTH_INPUT


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(
            ClientError(
                error_response={"Error": {"Code": "InvalidAccessKeyId"}},
                operation_name="head_bucket",
            ),
            "invalid_credentials",
            id="invalid_credentials",
        ),
        pytest.param(
            EndpointConnectionError(endpoint_url="http://example.com"),
            "cannot_connect",
            id="cannot_connect",
        ),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test reauthentication errors and recovery."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_client.head_bucket.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.head_bucket.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == USER_INPUT | REAUTH_INPUT


async def test_flow_bucket_not_found(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test a missing bucket is reported on the bucket field."""
    mock_client.head_bucket.side_effect = ClientError(
        error_response={"Error": {"Code": "404"}},
        operation_name="head_bucket",
    )
    result = await _async_start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BUCKET: "bucket_not_found"}

    mock_client.head_bucket.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


RECONFIGURE_INPUT = USER_INPUT | {
    CONF_BUCKET: "new-bucket",
    CONF_SECRET_ACCESS_KEY: "NewR2SecretAccessKey",
}


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring the bucket and credentials."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT | {CONF_PREFIX: ""}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == RECONFIGURE_INPUT
    assert mock_config_entry.title == "new-bucket"


async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test reconfigure shows validation errors and can recover."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_client.head_bucket.side_effect = ClientError(
        error_response={"Error": {"Code": "NoSuchBucket"}},
        operation_name="head_bucket",
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BUCKET: "bucket_not_found"}

    mock_client.head_bucket.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == RECONFIGURE_INPUT


async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure aborts when another entry uses the same bucket."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN, title="new-bucket", data=RECONFIGURE_INPUT
    ).add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
