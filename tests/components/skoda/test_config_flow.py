"""Test the Škoda config flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from skoda_public_api.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
    OpenApiForbiddenError,
    OpenApiRateLimitError,
    OpenApiServerError,
    OpenApiTimeoutError,
    OpenApiVehicleNotFoundError,
)
from skoda_public_api.models.vehicle import VehicleResponse

from homeassistant import config_entries
from homeassistant.components.skoda.const import CONF_VIN, DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VIN = "TMBJM7NP2M1TMP511"
API_KEY = "test-api-key"

USER_INPUT = {
    CONF_VIN: VIN,
    CONF_API_KEY: API_KEY,
}

VEHICLE_WITH_NAME = SimpleNamespace(vehicle=SimpleNamespace(name="Superb"))
VEHICLE_WITHOUT_NAME = SimpleNamespace(vehicle=SimpleNamespace(name=None))


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


def _patch_get_vehicle(
    request: pytest.FixtureRequest, *, side_effect=None, return_value=None
) -> AsyncMock:
    """Mock OpenAPIClient.get_vehicle, unpatched automatically after the test."""
    mock = AsyncMock(side_effect=side_effect, return_value=return_value)
    patcher = patch(
        "homeassistant.components.skoda.config_flow.OpenAPIClient.get_vehicle",
        mock,
    )
    patcher.start()
    request.addfinalizer(patcher.stop)
    return mock


async def test_form_shown(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await _init_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, request: pytest.FixtureRequest
) -> None:
    """Test successful flow with a vehicle that reports its name."""
    _patch_get_vehicle(request, return_value=VEHICLE_WITH_NAME)

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Škoda Superb"
    assert result["data"] == {
        CONF_VIN: VIN,
        CONF_API_KEY: API_KEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_success_without_vehicle_name(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    request: pytest.FixtureRequest,
) -> None:
    """Test successful flow falls back to the VIN when the name is missing."""
    _patch_get_vehicle(request, return_value=VEHICLE_WITHOUT_NAME)

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Škoda {VIN}"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_vin_length(hass: HomeAssistant) -> None:
    """Test the VIN length is validated before contacting the API."""
    result = await _init_flow(hass)
    result = await _configure_flow(
        hass, result["flow_id"], {**USER_INPUT, CONF_VIN: VIN[:-1]}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_VIN: "invalid_vin_length"}


async def test_duplicate_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, request: pytest.FixtureRequest
) -> None:
    """Test that the same VIN cannot be configured twice."""
    _patch_get_vehicle(request, return_value=VEHICLE_WITH_NAME)

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY

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
    request: pytest.FixtureRequest,
) -> None:
    """Test API failures surface the correct error on the form."""
    mock = _patch_get_vehicle(request, side_effect=exception)

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert mock.await_count == 1
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_error_recovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, request: pytest.FixtureRequest
) -> None:
    """Test the flow recovers after a failed attempt and completes on retry."""
    mock = _patch_get_vehicle(
        request, side_effect=[OpenApiAuthenticationError(), VEHICLE_WITH_NAME]
    )

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Škoda Superb"
    assert mock.await_count == 2
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vehicle_response: VehicleResponse,
    request: pytest.FixtureRequest,
) -> None:
    """Test a successful reauth updates the stored API key and reloads the entry."""
    mock_config_entry.add_to_hass(hass)
    _patch_get_vehicle(request, return_value=mock_vehicle_response)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


async def test_reauth_invalid_auth_shows_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    request: pytest.FixtureRequest,
) -> None:
    """Test an invalid API key during reauth keeps the form with an error."""
    mock_config_entry.add_to_hass(hass)
    _patch_get_vehicle(request, side_effect=OpenApiAuthenticationError())

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "still-bad-key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}
