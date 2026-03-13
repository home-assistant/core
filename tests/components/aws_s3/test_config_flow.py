"""Test the AWS S3 config flow."""

from unittest.mock import AsyncMock, patch

from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    ParamValidationError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.aws_s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_PREFIX,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CONFIG_ENTRY_DATA, USER_INPUT

from tests.common import MockConfigEntry

REAUTH_INPUT = {
    CONF_ACCESS_KEY_ID: "New-TestTest",
    CONF_SECRET_ACCESS_KEY: "New-TestTestTest",
}


async def _async_start_flow(
    hass: HomeAssistant,
    user_input: dict[str, str] | None = None,
) -> config_entries.ConfigFlowResult:
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


async def _async_start_flow_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    user_input: dict[str, str] | None = None,
) -> config_entries.ConfigFlowResult:
    """Initialize the reauth flow."""
    if user_input is None:
        user_input = REAUTH_INPUT

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )


@pytest.mark.parametrize(
    ("user_input", "expected_title", "expected_data"),
    [
        (USER_INPUT, "test", CONFIG_ENTRY_DATA),
        (
            USER_INPUT | {CONF_PREFIX: "my-prefix"},
            "test - my-prefix",
            USER_INPUT | {CONF_PREFIX: "my-prefix"},
        ),
        (
            USER_INPUT | {CONF_PREFIX: "/backups/"},
            "test - backups",
            CONFIG_ENTRY_DATA | {CONF_PREFIX: "backups"},
        ),
        (
            USER_INPUT | {CONF_PREFIX: "/"},
            "test",
            CONFIG_ENTRY_DATA,
        ),
        (
            USER_INPUT | {CONF_PREFIX: "my-prefix/"},
            "test - my-prefix",
            CONFIG_ENTRY_DATA | {CONF_PREFIX: "my-prefix"},
        ),
    ],
    ids=[
        "no_prefix",
        "with_prefix",
        "with_leading_and_trailing_slash",
        "only_slash",
        "with_trailing_slash",
    ],
)
async def test_flow(
    hass: HomeAssistant,
    user_input: dict,
    expected_title: str,
    expected_data: dict,
) -> None:
    """Test config flow with and without prefix, including prefix normalization."""
    result = await _async_start_flow(hass, user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == expected_data


@pytest.mark.parametrize(
    ("mock_target", "exception", "errors"),
    [
        (
            "aiobotocore.session.AioSession.create_client.return_value.head_bucket",
            ParamValidationError(report="Invalid bucket name"),
            {CONF_BUCKET: "invalid_bucket_name"},
        ),
        (
            "aiobotocore.session.AioSession.create_client",
            ValueError(),
            {
                CONF_ENDPOINT_URL: "invalid_endpoint_url",
            },
        ),
        (
            "aiobotocore.session.AioSession.create_client",
            EndpointConnectionError(endpoint_url="http://example.com"),
            {CONF_ENDPOINT_URL: "cannot_connect"},
        ),
        (
            "aiobotocore.session.AioSession.create_client.return_value.head_bucket",
            ClientError(
                error_response={"Error": {"Code": "InvalidAccessKeyId"}},
                operation_name="head_bucket",
            ),
            {"base": "invalid_credentials"},
        ),
    ],
    ids=[
        "invalid_bucket_name",
        "invalid_endpoint_url",
        "cannot_connect",
        "invalid_credentials",
    ],
)
async def test_flow_create_client_errors(
    hass: HomeAssistant,
    mock_target: str,
    exception: Exception,
    errors: dict[str, str],
) -> None:
    """Test config flow errors."""
    with patch(mock_target, side_effect=exception):
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
    assert result["data"] == CONFIG_ENTRY_DATA


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
    ("endpoint_url"),
    [
        ("@@@"),
        ("http://example.com"),
    ],
)
async def test_flow_create_not_aws_endpoint(
    hass: HomeAssistant, endpoint_url: str
) -> None:
    """Test config flow with a not aws endpoint should raise an error."""
    result = await _async_start_flow(
        hass, USER_INPUT | {CONF_ENDPOINT_URL: endpoint_url}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ENDPOINT_URL: "invalid_endpoint_url"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == CONFIG_ENTRY_DATA


async def test_abort_if_already_configured_with_same_prefix(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test we abort if same bucket, endpoint, and prefix are already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_ENTRY_DATA | {CONF_PREFIX: "my-prefix"},
    )
    entry.add_to_hass(hass)
    result = await _async_start_flow(hass, USER_INPUT | {CONF_PREFIX: "my-prefix"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_abort_if_entry_without_prefix(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test we abort if an entry without prefix matches bucket and endpoint."""
    # Entry without CONF_PREFIX in data (empty prefix is not persisted)
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA)
    entry.add_to_hass(hass)
    # Try to configure the same bucket/endpoint with an empty prefix
    result = await _async_start_flow(hass, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_abort_if_different_prefix(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test we do not abort when same bucket+endpoint but a different prefix is used."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_ENTRY_DATA | {CONF_PREFIX: "prefix-a"},
    )
    entry.add_to_hass(hass)
    result = await _async_start_flow(hass, USER_INPUT | {CONF_PREFIX: "prefix-b"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PREFIX] == "prefix-b"


async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test successful reauthentication."""
    mock_config_entry.add_to_hass(hass)

    result = await _async_start_flow_reauth(hass, mock_config_entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_ACCESS_KEY_ID] == "New-TestTest"
    assert mock_config_entry.data[CONF_SECRET_ACCESS_KEY] == "New-TestTestTest"
    # Bucket and endpoint remain unchanged
    assert mock_config_entry.data[CONF_BUCKET] == USER_INPUT[CONF_BUCKET]
    assert mock_config_entry.data[CONF_ENDPOINT_URL] == USER_INPUT[CONF_ENDPOINT_URL]


@pytest.mark.parametrize(
    ("mock_target", "exception", "errors"),
    [
        (
            "aiobotocore.session.AioSession.create_client.return_value.head_bucket",
            ParamValidationError(report="Invalid bucket name"),
            {"base": "invalid_bucket_name"},
        ),
        (
            "aiobotocore.session.AioSession.create_client",
            EndpointConnectionError(endpoint_url="http://example.com"),
            {"base": "cannot_connect"},
        ),
        (
            "aiobotocore.session.AioSession.create_client.return_value.head_bucket",
            ClientError(
                error_response={"Error": {"Code": "InvalidAccessKeyId"}},
                operation_name="head_bucket",
            ),
            {"base": "invalid_credentials"},
        ),
    ],
    ids=[
        "invalid_bucket_name",
        "cannot_connect",
        "invalid_credentials",
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_target: str,
    exception: Exception,
    errors: dict[str, str],
) -> None:
    """Test reauthentication with errors, then success."""
    mock_config_entry.add_to_hass(hass)

    with patch(mock_target, side_effect=exception):
        result = await _async_start_flow_reauth(hass, mock_config_entry)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    # Fix credentials and retry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
