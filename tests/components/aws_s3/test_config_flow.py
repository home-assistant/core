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
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_PREFIX,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CONFIG_ENTRY_DATA, USER_INPUT

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


@pytest.mark.parametrize(
    ("prefix_value", "expected_title", "expected_has_prefix"),
    [
        (None, "test", False),
        ("my-prefix", "test - my-prefix", True),
    ],
    ids=["no_prefix", "with_prefix"],
)
async def test_flow(
    hass: HomeAssistant,
    prefix_value: str | None,
    expected_title: str,
    expected_has_prefix: bool,
) -> None:
    """Test config flow with and without prefix."""
    user_input = USER_INPUT.copy()
    if prefix_value is not None:
        user_input = user_input | {CONF_PREFIX: prefix_value}

    result = await _async_start_flow(hass, user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title

    if expected_has_prefix:
        assert result["data"][CONF_PREFIX] == prefix_value
        assert result["data"] == user_input
    else:
        assert CONF_PREFIX not in result["data"]
        assert result["data"] == CONFIG_ENTRY_DATA


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
    assert result["data"] == CONFIG_ENTRY_DATA


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


async def test_flow_create_not_aws_endpoint(
    hass: HomeAssistant,
) -> None:
    """Test config flow with a not aws endpoint should raise an error."""
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


@pytest.mark.parametrize(
    ("input_prefix", "expected_prefix", "expected_title"),
    [
        ("/backups/", "backups", "test - backups"),
        ("/", None, "test"),
        ("my-prefix/", "my-prefix", "test - my-prefix"),
    ],
)
async def test_flow_prefix_normalization(
    hass: HomeAssistant,
    input_prefix: str,
    expected_prefix: str,
    expected_title: str,
) -> None:
    """Test that leading/trailing slashes are stripped from the prefix."""
    result = await _async_start_flow(hass, USER_INPUT | {CONF_PREFIX: input_prefix})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    if expected_prefix is not None:
        assert result["data"][CONF_PREFIX] == expected_prefix
    else:
        assert CONF_PREFIX not in result["data"]
