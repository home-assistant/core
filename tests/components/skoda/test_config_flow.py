"""Test the Škoda config flow."""

from unittest.mock import AsyncMock

from probatio import to_field_list
import pytest
from pytest_homeassistant.common import MockConfigEntry
from skoda_public_api.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
    OpenApiForbiddenError,
    OpenApiRateLimitError,
    OpenApiServerError,
    OpenApiTimeoutError,
    OpenApiVehicleNotFoundError,
)

from homeassistant import config_entries
from homeassistant.components.skoda.const import CONF_VIN, DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv

VIN = "TMBJM7NP2M1TMP511"
API_KEY = "test-api-key"

USER_INPUT = {
    CONF_VIN: VIN,
    CONF_API_KEY: API_KEY,
}


async def _init_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Start the user config flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def _configure_flow(
    hass: HomeAssistant, flow_id: str, user_input: dict | None = None
) -> ConfigFlowResult:
    """Submit the vehicle data form."""
    return await hass.config_entries.flow.async_configure(
        flow_id, USER_INPUT if user_input is None else user_input
    )


async def test_form_shown(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await _init_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


def _serialized_api_key_field(result: ConfigFlowResult) -> dict:
    """Return the API key field as the frontend receives it."""
    fields = to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    return next(
        field
        for field in fields
        if isinstance(field, dict) and field["name"] == CONF_API_KEY
    )


async def test_user_form_masks_api_key(hass: HomeAssistant) -> None:
    """Test the API key is entered in a masked password field."""
    result = await _init_flow(hass)

    assert _serialized_api_key_field(result)["selector"]["text"]["type"] == "password"


@pytest.mark.usefixtures("mock_skoda_client")
async def test_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful flow with a vehicle that reports its name."""
    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Škoda Enyaq Coupé"
    assert result["result"].unique_id == VIN
    assert result["data"] == {
        CONF_VIN: VIN,
        CONF_API_KEY: API_KEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_success_without_vehicle_name(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test successful flow falls back to the VIN when the name is missing."""
    mock_skoda_client.get_vehicle.return_value.vehicle.name = None

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Škoda {VIN}"
    assert result["result"].unique_id == VIN
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_vin_length(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test the VIN length is validated before contacting the API."""
    result = await _init_flow(hass)
    result = await _configure_flow(
        hass, result["flow_id"], {**USER_INPUT, CONF_VIN: VIN[:-1]}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_VIN: "invalid_vin_length"}
    mock_skoda_client.get_vehicle.assert_not_called()

    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == VIN
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_skoda_client")
async def test_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the same VIN cannot be configured twice."""
    mock_config_entry.add_to_hass(hass)

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        pytest.param(OpenApiTimeoutError(), "timeout_connect", id="timeout"),
        pytest.param(OpenApiAuthenticationError(), "invalid_auth", id="invalid_auth"),
        pytest.param(
            OpenApiForbiddenError(), "access_forbidden", id="access_forbidden"
        ),
        pytest.param(
            OpenApiVehicleNotFoundError(),
            "vehicle_not_found",
            id="vehicle_not_found",
        ),
        pytest.param(
            OpenApiRateLimitError(), "rate_limit_exceeded", id="rate_limit_exceeded"
        ),
        pytest.param(
            OpenApiServerError("server error"), "cannot_connect", id="server_error"
        ),
        pytest.param(OpenApiError("bad request"), "api_error", id="api_error"),
        pytest.param(RuntimeError("unexpected"), "unknown", id="unknown"),
    ],
)
async def test_api_errors(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
    mock_setup_entry: AsyncMock,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test API failures show an error and the flow recovers on retry."""
    mock_skoda_client.get_vehicle.side_effect = exception

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_skoda_client.get_vehicle.side_effect = None
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Škoda Enyaq Coupé"
    assert result["result"].unique_id == VIN
    assert mock_skoda_client.get_vehicle.await_count == 2
    assert len(mock_setup_entry.mock_calls) == 1
