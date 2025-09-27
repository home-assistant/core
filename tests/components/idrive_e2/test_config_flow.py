"""Test the IDrive e2 config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import boto3
from botocore.exceptions import EndpointConnectionError
from idrive_e2 import CannotConnect, InvalidAuth
import pytest

from homeassistant.components.idrive_e2 import ClientError
from homeassistant.components.idrive_e2.config_flow import (
    CONF_ACCESS_KEY_ID,
    IDriveE2ConfigFlow,
    _list_buckets,
)
from homeassistant.components.idrive_e2.const import (
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType

from .const import USER_INPUT

from tests.common import MockConfigEntry


def test_list_buckets_success() -> None:
    """Test _list_buckets returns bucket names."""
    mock_client = MagicMock()
    mock_client.list_buckets.return_value = {
        "Buckets": [{"Name": "bucket1"}, {"Name": "bucket2"}]
    }
    with patch.object(boto3.session.Session, "client", return_value=mock_client):
        buckets = _list_buckets(
            USER_INPUT[CONF_ENDPOINT_URL],
            USER_INPUT[CONF_ACCESS_KEY_ID],
            USER_INPUT[CONF_SECRET_ACCESS_KEY],
        )
        assert buckets == ["bucket1", "bucket2"]


def test_list_buckets_empty() -> None:
    """Test _list_buckets returns empty list if no buckets."""
    mock_client = MagicMock()
    mock_client.list_buckets.return_value = {"Buckets": []}
    with patch.object(boto3.session.Session, "client", return_value=mock_client):
        buckets = _list_buckets(
            USER_INPUT[CONF_ENDPOINT_URL],
            USER_INPUT[CONF_ACCESS_KEY_ID],
            USER_INPUT[CONF_SECRET_ACCESS_KEY],
        )
        assert buckets == []


def test_list_buckets_missing_name() -> None:
    """Test _list_buckets skips buckets without Name."""
    mock_client = MagicMock()
    mock_client.list_buckets.return_value = {"Buckets": [{}]}
    with patch.object(boto3.session.Session, "client", return_value=mock_client):
        buckets = _list_buckets(
            USER_INPUT[CONF_ENDPOINT_URL],
            USER_INPUT[CONF_ACCESS_KEY_ID],
            USER_INPUT[CONF_SECRET_ACCESS_KEY],
        )
        assert buckets == []


async def _async_start_flow(
    hass: HomeAssistant,
    user_input: dict[str, str] | None = None,
    bucket: str | None = None,
    exception: Exception | None = None,
) -> FlowResultType:
    """Initialize the config flow with both user and bucket steps."""
    # If user_input is None, test the initial form
    if user_input is None and exception is None:
        flow = IDriveE2ConfigFlow()
        flow.hass = hass
        return await flow.async_step_user()

    # Instantiate the flow directly
    if user_input is None:
        user_input = USER_INPUT
    flow = IDriveE2ConfigFlow()
    flow.hass = hass
    selected = bucket or user_input[CONF_BUCKET]

    # Step 1: submit user credentials
    mock_session = AsyncMock()
    with patch(
        "homeassistant.components.idrive_e2.config_flow.async_get_clientsession",
        return_value=mock_session,
    ):
        is_bucket_exception = isinstance(
            exception, (EndpointConnectionError, ValueError, ClientError)
        )

        # Patch the IDriveE2Client class instantiated by the flow for the endpoint URL
        mock_client = AsyncMock()
        if exception is not None and not is_bucket_exception:
            mock_client.get_region_endpoint = AsyncMock(side_effect=exception)
        else:
            mock_client.get_region_endpoint = AsyncMock(
                return_value=user_input[CONF_ENDPOINT_URL]
            )

        with patch(
            "homeassistant.components.idrive_e2.config_flow.IDriveE2Client",
            return_value=mock_client,
        ):
            patch_kwargs = (
                {"side_effect": exception}
                if is_bucket_exception
                else {"return_value": [selected]}
            )
            with patch(
                "homeassistant.components.idrive_e2.config_flow._list_buckets",
                **patch_kwargs,
            ):
                result = await flow.async_step_user(
                    {
                        "access_key_id": user_input["access_key_id"],
                        "secret_access_key": user_input["secret_access_key"],
                    }
                )

    # If the error is from the bucket step, the flow returns to the user step (FORM).
    if is_bucket_exception:
        return result

    # No exception: proceed into the bucket step
    if not exception:
        assert result["step_id"] == "bucket"
        with patch(
            "homeassistant.components.idrive_e2.config_flow._list_buckets",
            return_value=[selected],
        ):
            try:
                return await flow.async_step_bucket({CONF_BUCKET: selected})
            except Exception as err:
                if isinstance(err, AbortFlow):
                    return {"type": FlowResultType.ABORT, "reason": err.reason}
                raise

    return result


async def test_flow(hass: HomeAssistant) -> None:
    """Test config flow."""
    result = await _async_start_flow(hass, user_input=USER_INPUT)
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
async def test_flow_bucket_step_errors(
    hass: HomeAssistant,
    exception: Exception,
    errors: dict[str, str],
) -> None:
    """Test config flow errors."""
    result = await _async_start_flow(hass, exception=exception)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == errors

    # Fix and finish the test
    result = await _async_start_flow(hass, user_input=USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (InvalidAuth("Invalid credentials"), "invalid_credentials"),
        (CannotConnect("cannot connect"), "cannot_connect"),
    ],
)
async def test_flow_get_region_endpoint_error(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test user step error mapping when resolving region endpoint via client."""
    result = await _async_start_flow(hass, exception=exception)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Fix and finish the test
    result = await _async_start_flow(hass, user_input=USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == USER_INPUT


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if the account is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await _async_start_flow(hass, user_input=USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_user_initial_form(hass: HomeAssistant) -> None:
    """Test that the initial user step shows the form with no errors and correct schema."""
    result = await _async_start_flow(hass, user_input=None)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert "data_schema" in result
