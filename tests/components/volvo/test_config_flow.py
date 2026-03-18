"""Test the Volvo config flow."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.auth import AUTHORIZE_URL, TOKEN_URL
from volvocarsapi.models import VolvoApiException, VolvoCarsVehicle
from volvocarsapi.scopes import DEFAULT_SCOPES
from yarl import URL

from homeassistant import config_entries
from homeassistant.components.volvo.const import CONF_VIN, DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import async_load_fixture_as_json, configure_mock
from .const import (
    CLIENT_ID,
    DEFAULT_API_KEY,
    DEFAULT_MODEL,
    DEFAULT_VIN,
    REDIRECT_URI,
    SERVER_TOKEN_RESPONSE,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    mock_setup_entry: AsyncMock,
    mock_config_flow_api: VolvoCarsApi,
) -> None:
    """Check full flow."""
    result = await _async_run_flow_to_completion(
        hass, config_flow, mock_config_flow_api
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_KEY] == DEFAULT_API_KEY
    assert result["data"][CONF_VIN] == DEFAULT_VIN
    assert result["context"]["unique_id"] == DEFAULT_VIN


@pytest.mark.usefixtures("current_request_with_host")
async def test_single_vin_flow(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    mock_setup_entry: AsyncMock,
    mock_config_flow_api: VolvoCarsApi,
) -> None:
    """Check flow where API returns a single VIN."""
    _configure_mock_vehicles_success(mock_config_flow_api, single_vin=True)

    # Since there is only one VIN, the api_key step is the only step
    result = await hass.config_entries.flow.async_configure(config_flow["flow_id"])
    assert result["step_id"] == "api_key"

    result = await hass.config_entries.flow.async_configure(
        config_flow["flow_id"], {CONF_API_KEY: "abcdef0123456879abcdef"}
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(("api_key_failure"), [pytest.param(True), pytest.param(False)])
@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_flow_api: VolvoCarsApi,
    api_key_failure: bool,
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
        hass,
        result,
        mock_config_flow_api,
        has_vin_step=False,
        is_reauth=True,
        api_key_failure=api_key_failure,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_no_stale_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_flow_api: VolvoCarsApi,
) -> None:
    """Test if reauthentication flow does not use stale data."""
    old_access_token = mock_config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]

    with patch(
        "homeassistant.components.volvo.config_flow._create_volvo_cars_api",
        return_value=mock_config_flow_api,
    ) as mock_create_volvo_cars_api:
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
            hass,
            result,
            mock_config_flow_api,
            has_vin_step=False,
            is_reauth=True,
        )

        assert mock_create_volvo_cars_api.called
        call = mock_create_volvo_cars_api.call_args_list[0]
        access_token_arg = call.args[1]
        assert old_access_token != access_token_arg


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_flow_api: VolvoCarsApi,
) -> None:
    """Test reconfiguration flow."""
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "api_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "abcdef0123456879abcdef"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("current_request_with_host", "mock_config_entry")
async def test_unique_id_flow(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    mock_config_flow_api: VolvoCarsApi,
) -> None:
    """Test unique ID flow."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await _async_run_flow_to_completion(
        hass, config_flow, mock_config_flow_api
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_api_failure_flow(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    mock_config_flow_api: VolvoCarsApi,
) -> None:
    """Check flow where API throws an exception."""
    _configure_mock_vehicles_failure(mock_config_flow_api)

    result = await hass.config_entries.flow.async_configure(config_flow["flow_id"])
    assert result["step_id"] == "api_key"

    result = await hass.config_entries.flow.async_configure(
        config_flow["flow_id"], {CONF_API_KEY: "abcdef0123456879abcdef"}
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_load_vehicles"
    assert result["step_id"] == "api_key"

    result = await _async_run_flow_to_completion(
        hass, result, mock_config_flow_api, configure=False
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.fixture
async def config_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> config_entries.ConfigFlowResult:
    """Initialize a new config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    result_url = URL(result["url"])
    assert f"{result_url.origin()}{result_url.path}" == AUTHORIZE_URL
    assert result_url.query["response_type"] == "code"
    assert result_url.query["client_id"] == CLIENT_ID
    assert result_url.query["redirect_uri"] == REDIRECT_URI
    assert result_url.query["state"] == state
    assert result_url.query["code_challenge"]
    assert result_url.query["code_challenge_method"] == "S256"
    assert result_url.query["scope"] == " ".join(DEFAULT_SCOPES)

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    return result


@pytest.fixture
async def mock_config_flow_api(hass: HomeAssistant) -> AsyncGenerator[AsyncMock]:
    """Mock API used in config flow."""
    with patch(
        "homeassistant.components.volvo.config_flow.VolvoCarsApi",
        autospec=True,
    ) as mock_api:
        api: VolvoCarsApi = mock_api.return_value

        _configure_mock_vehicles_success(api)

        vehicle_data = await async_load_fixture_as_json(hass, "vehicle", DEFAULT_MODEL)
        configure_mock(
            api.async_get_vehicle_details,
            return_value=VolvoCarsVehicle.from_dict(vehicle_data),
        )

        yield api


@pytest.fixture(autouse=True)
async def mock_auth_client(
    aioclient_mock: AiohttpClientMocker,
) -> AsyncGenerator[AsyncMock]:
    """Mock auth requests."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TOKEN_URL,
        json=SERVER_TOKEN_RESPONSE,
    )


async def _async_run_flow_to_completion(
    hass: HomeAssistant,
    config_flow: ConfigFlowResult,
    mock_config_flow_api: VolvoCarsApi,
    *,
    configure: bool = True,
    has_vin_step: bool = True,
    is_reauth: bool = False,
    api_key_failure: bool = False,
) -> ConfigFlowResult:
    if configure:
        if api_key_failure:
            _configure_mock_vehicles_failure(mock_config_flow_api)

        config_flow = await hass.config_entries.flow.async_configure(
            config_flow["flow_id"]
        )

    if is_reauth and not api_key_failure:
        return config_flow

    assert config_flow["type"] is FlowResultType.FORM
    assert config_flow["step_id"] == "api_key"

    _configure_mock_vehicles_success(mock_config_flow_api)
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


def _configure_mock_vehicles_success(
    mock_config_flow_api: VolvoCarsApi, single_vin: bool = False
) -> None:
    vins = [{"vin": DEFAULT_VIN}]

    if not single_vin:
        vins.append({"vin": "YV10000000AAAAAAA"})

    configure_mock(mock_config_flow_api.async_get_vehicles, return_value=vins)


def _configure_mock_vehicles_failure(mock_config_flow_api: VolvoCarsApi) -> None:
    configure_mock(
        mock_config_flow_api.async_get_vehicles, side_effect=VolvoApiException()
    )
