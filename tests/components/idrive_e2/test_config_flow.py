"""Test the IDrive e2 config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from botocore.exceptions import EndpointConnectionError
from idrive_e2 import CannotConnect, InvalidAuth
import pytest
import voluptuous as vol

from homeassistant.components.idrive_e2 import ClientError
from homeassistant.components.idrive_e2.config_flow import CONF_ACCESS_KEY_ID
from homeassistant.components.idrive_e2.const import (
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import SelectSelector

from .const import USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_idrive_client() -> Generator[AsyncMock]:
    """Patch IDriveE2Client to return a mocked client."""
    mock_client = AsyncMock()
    mock_client.get_region_endpoint.return_value = USER_INPUT[CONF_ENDPOINT_URL]

    with patch(
        "homeassistant.components.idrive_e2.config_flow.IDriveE2Client",
        return_value=mock_client,
    ):
        yield mock_client


async def test_flow(
    hass: HomeAssistant,
    mock_idrive_client: AsyncMock,
    mock_client: AsyncMock,
) -> None:
    """Test config flow success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ACCESS_KEY_ID: USER_INPUT[CONF_ACCESS_KEY_ID],
            CONF_SECRET_ACCESS_KEY: USER_INPUT[CONF_SECRET_ACCESS_KEY],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BUCKET: USER_INPUT[CONF_BUCKET]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize(
    ("exception", "errors"),
    [
        (
            ClientError(
                {"Error": {"Code": "403", "Message": "Forbidden"}}, "list_buckets"
            ),
            {"base": "invalid_credentials"},
        ),
        (ValueError(), {"base": "invalid_endpoint_url"}),
        (
            EndpointConnectionError(endpoint_url="http://example.com"),
            {"base": "cannot_connect"},
        ),
    ],
)
async def test_flow_list_buckets_errors(
    hass: HomeAssistant,
    mock_idrive_client: AsyncMock,
    mock_client: AsyncMock,
    exception: Exception,
    errors: dict[str, str],
) -> None:
    """Test errors when listing buckets."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # First attempt: fail
    mock_client.list_buckets.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_ACCESS_KEY_ID: USER_INPUT[CONF_ACCESS_KEY_ID],
            CONF_SECRET_ACCESS_KEY: USER_INPUT[CONF_SECRET_ACCESS_KEY],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == errors

    # Second attempt: fix and finish to CREATE_ENTRY
    mock_client.list_buckets.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_ACCESS_KEY_ID: USER_INPUT[CONF_ACCESS_KEY_ID],
            CONF_SECRET_ACCESS_KEY: USER_INPUT[CONF_SECRET_ACCESS_KEY],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_BUCKET: USER_INPUT[CONF_BUCKET]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == USER_INPUT


async def test_flow_no_buckets(
    hass: HomeAssistant,
    mock_idrive_client: AsyncMock,
    mock_client: AsyncMock,
) -> None:
    """Test we show an error when no buckets are returned."""
    # Start flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # First attempt: empty bucket list -> error
    mock_client.list_buckets.return_value = {"Buckets": []}
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_ACCESS_KEY_ID: USER_INPUT[CONF_ACCESS_KEY_ID],
            CONF_SECRET_ACCESS_KEY: USER_INPUT[CONF_SECRET_ACCESS_KEY],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_buckets"}

    # Second attempt: fix and finish to CREATE_ENTRY
    mock_client.list_buckets.return_value = {
        "Buckets": [{"Name": USER_INPUT[CONF_BUCKET]}]
    }
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_ACCESS_KEY_ID: USER_INPUT[CONF_ACCESS_KEY_ID],
            CONF_SECRET_ACCESS_KEY: USER_INPUT[CONF_SECRET_ACCESS_KEY],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_BUCKET: USER_INPUT[CONF_BUCKET]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == USER_INPUT


async def test_flow_bucket_step_options_from_s3_list_buckets(
    hass: HomeAssistant,
    mock_idrive_client: AsyncMock,
    mock_client: AsyncMock,
) -> None:
    """Test bucket step shows dropdown options coming from S3 list_buckets()."""
    # Start flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # S3 list_buckets returns our test payload
    mock_client.list_buckets.return_value = {
        "Buckets": [{"Name": "bucket1"}, {"Name": "bucket2"}]
    }

    # Submit credentials
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_ACCESS_KEY_ID: USER_INPUT[CONF_ACCESS_KEY_ID],
            CONF_SECRET_ACCESS_KEY: USER_INPUT[CONF_SECRET_ACCESS_KEY],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    # Extract dropdown options from selector in schema
    schema = result["data_schema"].schema
    selector = schema[vol.Required(CONF_BUCKET)]
    assert isinstance(selector, SelectSelector)

    cfg = selector.config
    options = cfg["options"] if isinstance(cfg, dict) else cfg.options

    assert options == ["bucket1", "bucket2"]

    # Continue to finish to CREATE_ENTRY
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_BUCKET: "bucket1"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "bucket1"
    assert result["data"][CONF_BUCKET] == "bucket1"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (InvalidAuth("Invalid credentials"), "invalid_credentials"),
        (CannotConnect("cannot connect"), "cannot_connect"),
    ],
)
async def test_flow_get_region_endpoint_error(
    hass: HomeAssistant,
    mock_idrive_client: AsyncMock,
    mock_client: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test user step error mapping when resolving region endpoint via client."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # First attempt: fail endpoint resolution
    mock_idrive_client.get_region_endpoint.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_ACCESS_KEY_ID: USER_INPUT[CONF_ACCESS_KEY_ID],
            CONF_SECRET_ACCESS_KEY: USER_INPUT[CONF_SECRET_ACCESS_KEY],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    # Second attempt: fix and finish to CREATE_ENTRY
    mock_idrive_client.get_region_endpoint.side_effect = None
    mock_idrive_client.get_region_endpoint.return_value = USER_INPUT[CONF_ENDPOINT_URL]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_ACCESS_KEY_ID: USER_INPUT[CONF_ACCESS_KEY_ID],
            CONF_SECRET_ACCESS_KEY: USER_INPUT[CONF_SECRET_ACCESS_KEY],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_BUCKET: USER_INPUT[CONF_BUCKET]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_idrive_client: AsyncMock,
    mock_client: AsyncMock,
) -> None:
    """Test we abort if the account is already configured."""
    # Existing entry that should cause abort when selecting the same bucket + endpoint
    MockConfigEntry(
        domain=mock_config_entry.domain,
        title=mock_config_entry.title,
        data={
            **mock_config_entry.data,
            CONF_BUCKET: USER_INPUT[CONF_BUCKET],
            CONF_ENDPOINT_URL: USER_INPUT[CONF_ENDPOINT_URL],
        },
        unique_id="existing",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ACCESS_KEY_ID: USER_INPUT[CONF_ACCESS_KEY_ID],
            CONF_SECRET_ACCESS_KEY: USER_INPUT[CONF_SECRET_ACCESS_KEY],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BUCKET: USER_INPUT[CONF_BUCKET]},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
