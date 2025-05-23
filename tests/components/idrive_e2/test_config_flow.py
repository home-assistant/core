"""Test the IDrive e2 config flow."""

from unittest.mock import AsyncMock, patch

from aiohttp import RequestInfo
from aiohttp.client_exceptions import ClientError, ClientResponseError
from botocore.exceptions import EndpointConnectionError, ParamValidationError
import pytest

from homeassistant.components.idrive_e2.config_flow import IDriveE2ConfigFlow
from homeassistant.components.idrive_e2.const import CONF_BUCKET, CONF_ENDPOINT_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType

from .const import USER_INPUT

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import URL, CIMultiDict


async def _async_start_flow(
    hass: HomeAssistant,
    user_input: dict[str, str] | None = None,
    bucket: str | None = None,
    exception: Exception | None = None,
) -> FlowResultType:
    """Initialize the config flow with both user and bucket steps."""
    if user_input is None:
        user_input = USER_INPUT

    # Instantiate the flow directly

    flow = IDriveE2ConfigFlow()
    flow.hass = hass
    selected = bucket or user_input[CONF_BUCKET]

    # Step 1: submit user credentials
    mock_session = AsyncMock()
    with patch(
        "homeassistant.components.idrive_e2.config_flow.async_get_clientsession",
        return_value=mock_session,
    ):
        # Mock the exception for the get_region_endpoint_url call
        if isinstance(exception, ClientError):
            mock_session.post.side_effect = exception
            return await flow.async_step_user(
                {
                    "access_key_id": user_input["access_key_id"],
                    "secret_access_key": user_input["secret_access_key"],
                }
            )

        # Normal response
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json = AsyncMock(
            return_value={"domain_name": user_input[CONF_ENDPOINT_URL]}
        )
        mock_session.post.return_value = mock_response

        patch_kwargs = (
            {"side_effect": exception} if exception else {"return_value": [selected]}
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

    if not exception:
        assert result["step_id"] == "bucket"
        with patch(
            "homeassistant.components.idrive_e2.config_flow._list_buckets",
            return_value=[selected],
        ):
            # Show the bucket form
            try:
                return await flow.async_step_bucket({CONF_BUCKET: selected})
            except Exception as err:
                # Convert abort flow exception to an abort result
                if isinstance(err, AbortFlow):
                    return {"type": FlowResultType.ABORT, "reason": err.reason}
                raise

    return result


async def test_flow(hass: HomeAssistant) -> None:
    """Test config flow."""
    result = await _async_start_flow(hass)
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
    result = await _async_start_flow(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (
            ClientResponseError(
                request_info=RequestInfo(
                    url=URL("https://example.com"),
                    method="POST",
                    headers=CIMultiDict(),
                ),
                history=(),
                status=401,
                message="Invalid credentials",
            ),
            "invalid_credentials",
        ),
        (
            ClientError(),
            "cannot_connect",
        ),
    ],
)
async def test_flow_get_region_endpoint_url_error(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test setup_entry error when calling head_bucket."""
    result = await _async_start_flow(hass, exception=exception)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Fix and finish the test
    result = await _async_start_flow(hass)

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
