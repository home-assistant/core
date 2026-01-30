"""Test the IDrive e2 config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from botocore.exceptions import EndpointConnectionError
from idrive_e2 import CannotConnect, InvalidAuth
import pytest
import voluptuous as vol

from homeassistant.components.idrive_e2 import ClientError
from homeassistant.components.idrive_e2.config_flow import (
    CONF_ACCESS_KEY_ID,
    SelectSelector,
)
from homeassistant.components.idrive_e2.const import (
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_aiobotocore_s3_client() -> Generator[AsyncMock]:
    """Patch AioSession.create_client to return a mocked async context manager."""
    client = AsyncMock()
    with patch(
        "homeassistant.components.idrive_e2.config_flow.AioSession.create_client",
        return_value=_mock_aiobotocore_cm(client),
    ):
        yield client


@pytest.fixture
def mock_idrive_client() -> Generator[AsyncMock]:
    """Patch IDriveE2Client + aiohttp session, return the client mock."""
    mock_session = AsyncMock()
    mock_client = AsyncMock()
    with (
        patch(
            "homeassistant.components.idrive_e2.config_flow.async_get_clientsession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.idrive_e2.config_flow.IDriveE2Client",
            return_value=mock_client,
        ),
    ):
        yield mock_client


@pytest.fixture
def mock_list_buckets() -> Generator[AsyncMock]:
    """Patch _list_buckets, return the mock."""
    mock = AsyncMock()
    with patch(
        "homeassistant.components.idrive_e2.config_flow._list_buckets",
        new=mock,
    ):
        yield mock


def _mock_aiobotocore_cm(client: AsyncMock) -> MagicMock:
    """Return an async context manager yielding the provided client."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


async def _start_flow(hass: HomeAssistant) -> dict:
    """Start the flow via HA's flow manager."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def _submit_user(hass: HomeAssistant, flow_id: str) -> dict:
    """Submit the user step credentials."""
    return await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_ACCESS_KEY_ID: USER_INPUT[CONF_ACCESS_KEY_ID],
            CONF_SECRET_ACCESS_KEY: USER_INPUT[CONF_SECRET_ACCESS_KEY],
        },
    )


async def _submit_bucket(hass: HomeAssistant, flow_id: str, bucket: str) -> dict:
    """Submit the bucket selection."""
    return await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_BUCKET: bucket},
    )


async def test_flow(
    hass: HomeAssistant,
    mock_idrive_client: AsyncMock,
    mock_list_buckets: AsyncMock,
) -> None:
    """Test config flow success path."""
    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_idrive_client.get_region_endpoint.return_value = USER_INPUT[CONF_ENDPOINT_URL]
    mock_list_buckets.return_value = [USER_INPUT[CONF_BUCKET]]

    result = await _submit_user(hass, result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    result = await _submit_bucket(hass, result["flow_id"], USER_INPUT[CONF_BUCKET])
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
    mock_list_buckets: AsyncMock,
    exception: Exception,
    errors: dict[str, str],
) -> None:
    """Test errors when listing buckets."""
    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_idrive_client.get_region_endpoint.return_value = USER_INPUT[CONF_ENDPOINT_URL]
    mock_list_buckets.side_effect = exception

    result = await _submit_user(hass, result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == errors


async def test_flow_no_buckets(
    hass: HomeAssistant,
    mock_idrive_client: AsyncMock,
    mock_aiobotocore_s3_client: AsyncMock,
) -> None:
    """Test we show an error when no buckets are returned."""
    # Start flow
    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # User step: endpoint lookup succeeds
    mock_idrive_client.get_region_endpoint.return_value = USER_INPUT[CONF_ENDPOINT_URL]

    # S3 list_buckets returns no buckets
    mock_aiobotocore_s3_client.list_buckets.return_value = {"Buckets": []}

    # Submit credentials
    result = await _submit_user(hass, result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_buckets"}


async def test_flow_bucket_step_options_from_s3_list_buckets(
    hass: HomeAssistant,
    mock_idrive_client: AsyncMock,
    mock_aiobotocore_s3_client: AsyncMock,
) -> None:
    """Test bucket step shows dropdown options coming from S3 list_buckets()."""
    # Start flow
    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # User step: endpoint lookup succeeds
    mock_idrive_client.get_region_endpoint.return_value = USER_INPUT[CONF_ENDPOINT_URL]

    # S3 list_buckets returns our test payload
    mock_aiobotocore_s3_client.list_buckets.return_value = {
        "Buckets": [{"Name": "bucket1"}, {"Name": "bucket2"}]
    }

    # Submit credentials
    result = await _submit_user(hass, result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    # Extract dropdown options from selector in schema
    schema = result["data_schema"].schema
    selector = schema[vol.Required(CONF_BUCKET)]
    assert isinstance(selector, SelectSelector)

    cfg = selector.config
    options = cfg["options"] if isinstance(cfg, dict) else cfg.options

    assert options == ["bucket1", "bucket2"]


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
    exception: Exception,
    expected_error: str,
) -> None:
    """Test user step error mapping when resolving region endpoint via client."""
    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_idrive_client.get_region_endpoint.side_effect = exception

    result = await _submit_user(hass, result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_idrive_client: AsyncMock,
    mock_list_buckets: AsyncMock,
) -> None:
    """Test we abort if the account is already configured."""
    # Existing entry that should cause abort when selecting the same bucket + endpoint
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BUCKET: USER_INPUT[CONF_BUCKET],
            CONF_ENDPOINT_URL: USER_INPUT[CONF_ENDPOINT_URL],
        },
        unique_id="existing",
    ).add_to_hass(hass)

    result = await _start_flow(hass)

    mock_idrive_client.get_region_endpoint.return_value = USER_INPUT[CONF_ENDPOINT_URL]
    mock_list_buckets.return_value = [USER_INPUT[CONF_BUCKET]]

    result = await _submit_user(hass, result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    result = await _submit_bucket(hass, result["flow_id"], USER_INPUT[CONF_BUCKET])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_user_initial_form(hass: HomeAssistant) -> None:
    """Test initial user step shows the form with no errors and correct schema."""
    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert "data_schema" in result
