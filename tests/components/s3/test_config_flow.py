"""Test the S3 config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.s3._api import (
    CannotConnectError,
    InvalidBucketNameError,
    InvalidCredentialsError,
    InvalidEndpointURLError,
)
from homeassistant.components.s3.config_flow import _get_unique_id
from homeassistant.components.s3.const import CONF_BUCKET, CONF_ENDPOINT_URL, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import USER_INPUT

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("input_data", "expected_unique_id"),
    [
        (
            {
                CONF_BUCKET: "foo",
                CONF_ENDPOINT_URL: "https://s3.eu-central-1.amazonaws.com/",
            },
            "s3_eu_central_1_amazonaws_com.foo",
        ),
        (
            {
                CONF_BUCKET: "foo",
                CONF_ENDPOINT_URL: "http://127.0.0.1:9000/",
            },
            "127_0_0_1_9000.foo",
        ),
    ],
)
def test_get_unique_id(input_data: dict[str, str], expected_unique_id: str) -> None:
    """Test config entry IDs are unique tuples of (Endpoint + Bucket name)."""
    assert _get_unique_id(input_data) == expected_unique_id


async def _async_start_flow(
    hass: HomeAssistant,
) -> FlowResultType:
    """Initialize the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )


async def test_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test config flow."""
    result = await _async_start_flow(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize(
    ("exception", "errors"),
    [
        (InvalidCredentialsError, {"base": "invalid_credentials"}),
        (InvalidBucketNameError, {CONF_BUCKET: "invalid_bucket_name"}),
        (InvalidEndpointURLError, {CONF_ENDPOINT_URL: "invalid_endpoint_url"}),
        (CannotConnectError, {CONF_ENDPOINT_URL: "cannot_connect"}),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    errors: dict[str, str],
) -> None:
    """Test config flow errors."""
    with patch(
        "homeassistant.components.s3.config_flow.get_client",
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
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == USER_INPUT


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if the account is already configured."""
    result = await _async_start_flow(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await _async_start_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
