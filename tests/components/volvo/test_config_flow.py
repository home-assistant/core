"""Test the Volvo config flow."""

from unittest.mock import AsyncMock

import pytest
from volvocarsapi.api import _API_CONNECTED_ENDPOINT, _API_URL
from volvocarsapi.auth import TOKEN_URL
from volvocarsapi.models import VolvoApiException

from homeassistant.components.volvo.const import CONF_VIN, DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .common import load_json_object_fixture
from .const import DEFAULT_MODEL, DEFAULT_VIN, REDIRECT_URI, SERVER_TOKEN_RESPONSE

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check full flow."""
    config_flow = await _async_run_flow_to_completion(hass, config_flow, aioclient_mock)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert config_flow["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("current_request_with_host")
async def test_single_vin_flow(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check flow where API returns a single VIN."""
    _mock_api_client(aioclient_mock, single_vin=True)

    # Since there is only one VIN, the api_key step is the only step
    config_flow = await hass.config_entries.flow.async_configure(config_flow["flow_id"])
    assert config_flow["step_id"] == "api_key"

    config_flow = await hass.config_entries.flow.async_configure(
        config_flow["flow_id"], {CONF_API_KEY: "abcdef0123456879abcdef"}
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
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

    _mock_api_client(aioclient_mock)

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
        json=SERVER_TOKEN_RESPONSE,
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


async def _async_run_flow_to_completion(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    aioclient_mock: AiohttpClientMocker,
    *,
    has_vin_step: bool = True,
) -> ConfigFlowResult:
    _mock_api_client(aioclient_mock)

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
            config_flow["flow_id"], {CONF_VIN: DEFAULT_VIN}
        )

    return config_flow


def _mock_api_client(
    aioclient_mock: AiohttpClientMocker, single_vin: bool = False
) -> None:
    aioclient_mock.post(
        TOKEN_URL,
        json=SERVER_TOKEN_RESPONSE,
    )

    vins = [{"vin": DEFAULT_VIN}]

    if not single_vin:
        vins.append({"vin": "YV10000000AAAAAAA"})

    aioclient_mock.get(
        f"{_API_URL}{_API_CONNECTED_ENDPOINT}",
        json={
            "data": vins,
        },
    )

    vehicle_data = load_json_object_fixture("vehicle", DEFAULT_MODEL)
    aioclient_mock.get(
        f"{_API_URL}{_API_CONNECTED_ENDPOINT}/{DEFAULT_VIN}",
        json={
            "data": vehicle_data,
        },
    )

    vehicle_data = load_json_object_fixture("vehicle", "xc90_petrol_2019")
    aioclient_mock.get(
        f"{_API_URL}{_API_CONNECTED_ENDPOINT}/YV10000000AAAAAAA",
        json={
            "data": vehicle_data,
        },
    )
