"""Test the Volvo config flow."""

from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.volvo.const import (
    CONF_VIN,
    DOMAIN,
    OPT_FUEL_CONSUMPTION_UNIT,
    OPT_FUEL_UNIT_LITER_PER_100KM,
    OPT_FUEL_UNIT_MPG_UK,
    OPT_FUEL_UNIT_MPG_US,
)
from homeassistant.components.volvo.volvo_connected.api import (
    _API_CONNECTED_ENDPOINT,
    _API_URL,
)
from homeassistant.components.volvo.volvo_connected.auth import TOKEN_URL
from homeassistant.components.volvo.volvo_connected.models import VolvoApiException
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM, UnitSystem

from .const import REDIRECT_URI

from tests.common import METRIC_SYSTEM, MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("country", "units", "expected_fuel_unit"),
    [
        ("BE", METRIC_SYSTEM, OPT_FUEL_UNIT_LITER_PER_100KM),
        ("NL", METRIC_SYSTEM, OPT_FUEL_UNIT_LITER_PER_100KM),
        ("BE", US_CUSTOMARY_SYSTEM, OPT_FUEL_UNIT_MPG_US),
        ("UK", METRIC_SYSTEM, OPT_FUEL_UNIT_MPG_UK),
        ("UK", US_CUSTOMARY_SYSTEM, OPT_FUEL_UNIT_MPG_UK),
        ("US", US_CUSTOMARY_SYSTEM, OPT_FUEL_UNIT_MPG_US),
        ("US", METRIC_SYSTEM, OPT_FUEL_UNIT_MPG_US),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    *,
    country: str,
    units: UnitSystem,
    expected_fuel_unit: str,
) -> None:
    """Check full flow."""
    hass.config.country = country
    hass.config.units = units

    config_flow = await _async_run_flow_to_completion(hass, config_flow, aioclient_mock)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert config_flow["type"] is FlowResultType.CREATE_ENTRY
    assert config_flow["options"][OPT_FUEL_CONSUMPTION_UNIT] == expected_fuel_unit


@pytest.mark.usefixtures("current_request_with_host")
async def test_single_vin_flow(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check flow where API returns a single VIN."""
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    aioclient_mock.get(
        f"{_API_URL}{_API_CONNECTED_ENDPOINT}",
        json={
            "data": [{"vin": "YV123456789"}],
        },
    )

    # Since there is only one VIN, the api_key step is the only step
    config_flow = await hass.config_entries.flow.async_configure(config_flow["flow_id"])
    assert config_flow["step_id"] == "api_key"

    config_flow = await hass.config_entries.flow.async_configure(
        config_flow["flow_id"], {CONF_API_KEY: "abcdef0123456879abcdef"}
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauthentication flow."""
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await _async_run_flow_to_completion(
        hass, result, aioclient_mock, has_vin_step=False
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reconfiguration flow."""
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "api_key"

    aioclient_mock.get(
        f"{_API_URL}{_API_CONNECTED_ENDPOINT}",
        json={
            "data": [{"vin": "YV123456789"}, {"vin": "YV198765432"}],
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "abcdef0123456879abcdef"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("current_request_with_host", "mock_config_entry")
async def test_unique_id_flow(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test unique ID flow."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    config_flow = await _async_run_flow_to_completion(hass, config_flow, aioclient_mock)

    assert config_flow["type"] is FlowResultType.ABORT
    assert config_flow["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_api_failure_flow(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check flow where API throws an exception."""
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    aioclient_mock.get(
        f"{_API_URL}{_API_CONNECTED_ENDPOINT}",
        exc=VolvoApiException(),
    )

    config_flow = await hass.config_entries.flow.async_configure(config_flow["flow_id"])
    assert config_flow["step_id"] == "api_key"

    config_flow = await hass.config_entries.flow.async_configure(
        config_flow["flow_id"], {CONF_API_KEY: "abcdef0123456879abcdef"}
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert config_flow["type"] is FlowResultType.FORM
    assert config_flow["errors"]["base"] == "cannot_load_vehicles"
    assert config_flow["step_id"] == "api_key"


@pytest.mark.parametrize(
    ("fuel_unit"),
    [
        (OPT_FUEL_UNIT_LITER_PER_100KM),
        (OPT_FUEL_UNIT_MPG_UK),
        (OPT_FUEL_UNIT_MPG_US),
    ],
)
async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, fuel_unit: str
) -> None:
    """Test options flow."""
    mock_config_entry.runtime_data = AsyncMock()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={OPT_FUEL_CONSUMPTION_UNIT: fuel_unit}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[OPT_FUEL_CONSUMPTION_UNIT] == fuel_unit


async def test_no_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow where no options are available."""
    mock_config_entry.runtime_data = AsyncMock()
    mock_config_entry.runtime_data.coordinator = AsyncMock()
    mock_config_entry.runtime_data.coordinator.vehicle = AsyncMock()
    mock_config_entry.runtime_data.coordinator.vehicle.has_combustion_engine = Mock(
        return_value=False
    )

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_options_available"


async def _async_run_flow_to_completion(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    aioclient_mock: AiohttpClientMocker,
    *,
    has_vin_step: bool = True,
) -> ConfigFlowResult:
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )

    aioclient_mock.get(
        f"{_API_URL}{_API_CONNECTED_ENDPOINT}",
        json={
            "data": [{"vin": "YV123456789"}, {"vin": "YV198765432"}],
        },
    )

    config_flow = await hass.config_entries.flow.async_configure(config_flow["flow_id"])
    assert config_flow["type"] is FlowResultType.FORM
    assert config_flow["step_id"] == "api_key"

    config_flow = await hass.config_entries.flow.async_configure(
        config_flow["flow_id"], {CONF_API_KEY: "abcdef0123456879abcdef"}
    )

    if has_vin_step:
        assert config_flow["type"] is FlowResultType.FORM
        assert config_flow["step_id"] == "vin"

        config_flow = await hass.config_entries.flow.async_configure(
            config_flow["flow_id"], {CONF_VIN: "YV123456789"}
        )

    return config_flow
