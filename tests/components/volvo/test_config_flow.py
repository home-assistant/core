"""Test the Volvo config flow."""

from collections.abc import AsyncGenerator, Sequence
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.auth import LEGACY_VOLVOID_SERVER, VOLVOID_SERVER
from volvocarsapi.models import VolvoApiException, VolvoCarsVehicle
from volvocarsapi.scopes import ALL_SCOPES
from yarl import URL

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.cloud import (
    DATA_CLOUD,
    DOMAIN as CLOUD_DOMAIN,
    account_link,
)
from homeassistant.components.volvo.const import CONF_VIN, DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import async_load_fixture_as_json, configure_mock
from .const import (
    CLIENT_ID,
    CLIENT_SECRET,
    DEFAULT_API_KEY,
    DEFAULT_MODEL,
    DEFAULT_VIN,
    LEGACY_CLIENT_ID,
    REDIRECT_URI,
    SERVER_TOKEN_RESPONSE,
)


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
    assert result["result"].unique_id == DEFAULT_VIN


@pytest.mark.parametrize("client_id", [LEGACY_CLIENT_ID])
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_legacy_credential_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_flow_api: VolvoCarsApi,
) -> None:
    """Test that a legacy credential keeps using the legacy Volvo ID system."""
    aioclient_mock.post(LEGACY_VOLVOID_SERVER.token_url, json=SERVER_TOKEN_RESPONSE)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result_url = URL(result["url"])
    assert (
        f"{result_url.origin()}{result_url.path}" == LEGACY_VOLVOID_SERVER.authorize_url
    )
    assert result_url.query["client_id"] == LEGACY_CLIENT_ID
    assert result_url.query["scope"] == " ".join(ALL_SCOPES)

    client = await hass_client_no_auth()
    resp = await client.get(
        f"/auth/external/callback?code=abcd&state={result_url.query['state']}"
    )
    assert resp.status == 200

    result = await _async_run_flow_to_completion(hass, result, mock_config_flow_api)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEFAULT_VIN
    assert [call[1] for call in aioclient_mock.mock_calls] == [
        URL(LEGACY_VOLVOID_SERVER.token_url)
    ]


@pytest.mark.parametrize(
    ("authorize_url", "expected_scopes"),
    [
        pytest.param(
            f"{VOLVOID_SERVER.authorize_url}?client_id=vid-dc-cloud",
            VOLVOID_SERVER.all_scopes,
            id="new_client",
        ),
        pytest.param(
            f"{LEGACY_VOLVOID_SERVER.authorize_url}?client_id=dc-cloud",
            ALL_SCOPES,
            id="legacy_client",
        ),
        pytest.param("https://example.com/auth", ALL_SCOPES, id="no_client_id"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_account_linking_scopes(
    hass: HomeAssistant, authorize_url: str, expected_scopes: Sequence[str]
) -> None:
    """Test that account linking requests the scopes of the cloud's client ID."""
    hass.data[DATA_CLOUD] = Mock()
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, account_link.CloudOAuth2Implementation(hass, DOMAIN)
    )
    helper = Mock(
        async_get_authorize_url=AsyncMock(return_value=authorize_url),
        async_get_tokens=AsyncMock(side_effect=TimeoutError),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "pick_implementation"

    with patch(
        "hass_nabucasa.account_link.AuthorizeAccountHelper", return_value=helper
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"implementation": CLOUD_DOMAIN}
        )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert URL(result["url"]).query["scope"] == " ".join(expected_scopes)


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


@pytest.mark.parametrize("client_id", [LEGACY_CLIENT_ID])
@pytest.mark.usefixtures("current_request_with_host", "mock_config_flow_api")
async def test_reauth_flow_new_credential(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test reauth with a new credential always asks for the API key."""
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), "volvo_new"
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "pick_implementation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "volvo_new"}
    )

    client = await hass_client_no_auth()
    await client.get(
        f"/auth/external/callback?code=abcd&state={URL(result['url']).query['state']}"
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "api_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data["auth_implementation"] == "volvo_new"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


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
    assert f"{result_url.origin()}{result_url.path}" == VOLVOID_SERVER.authorize_url
    assert result_url.query["response_type"] == "code"
    assert result_url.query["client_id"] == CLIENT_ID
    assert result_url.query["redirect_uri"] == REDIRECT_URI
    assert result_url.query["state"] == state
    assert result_url.query["code_challenge"]
    assert result_url.query["code_challenge_method"] == "S256"
    assert result_url.query["scope"] == " ".join(VOLVOID_SERVER.all_scopes)

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
        VOLVOID_SERVER.token_url,
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
