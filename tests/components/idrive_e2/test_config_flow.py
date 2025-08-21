"""Test the IDrive e2 config flow."""

from unittest.mock import AsyncMock, patch

from botocore.exceptions import EndpointConnectionError, ParamValidationError
from idrive_e2 import CannotConnect, InvalidAuth
import pytest

from homeassistant.components.idrive_e2.config_flow import IDriveE2ConfigFlow
from homeassistant.components.idrive_e2.const import CONF_BUCKET, CONF_ENDPOINT_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType

from .const import USER_INPUT

from tests.common import MockConfigEntry


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
        is_bucket_exception = isinstance(
            exception, (ParamValidationError, EndpointConnectionError, ValueError)
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
