"""Test the Tesla Fleet config flow."""

from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from tesla_fleet_api.exceptions import (
    LoginRequired,
    PreconditionFailed,
    TeslaFleetError,
)

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.tesla_fleet.config_flow import OAuth2FlowHandler
from homeassistant.components.tesla_fleet.const import (
    AUTHORIZE_URL,
    DOMAIN,
    SCOPES,
    TOKEN_URL,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, get_schema_suggested_value
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT = "https://example.com/auth/external/callback"
UNIQUE_ID = "uid"
PUBLIC_KEY = (
    "0404112233445566778899aabbccddeeff112233445566778899aabbccddeeff"
    "112233445566778899aabbccddeeff112233445566778899aabbccddeeff1122"
)
DEFAULT_REGISTER_RESPONSE = object()


def _mock_api(
    mock_private_key: Mock,
    *,
    public_key: str = PUBLIC_KEY,
    server: str | None = None,
    register_response: dict[str, dict[str, str]] | None | object = (
        DEFAULT_REGISTER_RESPONSE
    ),
    register_side_effect: BaseException | type[BaseException] | None = None,
) -> AsyncMock:
    """Create a mocked Tesla Fleet API client."""
    mock_api = AsyncMock()
    mock_api.private_key = mock_private_key
    mock_api.get_private_key = AsyncMock()
    mock_api.partner_login = AsyncMock()
    mock_api.public_pem = "test_pem"
    mock_api.public_uncompressed_point = public_key
    mock_api.server = server
    if register_side_effect is not None:
        mock_api.partner.register.side_effect = register_side_effect
    elif register_response is DEFAULT_REGISTER_RESPONSE:
        mock_api.partner.register.return_value = {
            "response": {"public_key": public_key}
        }
    else:
        mock_api.partner.register.return_value = register_response
    return mock_api


def _tesla_error(data: str | dict[str, str]) -> TeslaFleetError:
    """Create a TeslaFleetError with a test payload."""
    return TeslaFleetError(data)


@pytest.fixture
async def access_token(hass: HomeAssistant) -> str:
    """Return a valid access token."""
    return config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "sub": UNIQUE_ID,
            "aud": [],
            "scp": [
                "vehicle_device_data",
                "vehicle_cmds",
                "vehicle_charging_cmds",
                "energy_device_data",
                "energy_cmds",
                "offline_access",
                "openid",
            ],
            "ou_code": "NA",
        },
    )


@pytest.fixture(autouse=True)
async def create_credential(hass: HomeAssistant) -> None:
    """Create a user credential."""
    # Create user application credential
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("user_client_id", "user_client_secret"),
        "user_cred",
    )


@pytest.fixture
def mock_private_key() -> Mock:
    """Mock private key for testing."""
    private_key = Mock()
    public_key = Mock()
    private_key.public_key.return_value = public_key
    public_key.public_bytes.side_effect = [
        b"-----BEGIN PUBLIC KEY-----\n"
        b"MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n"
        b"-----END PUBLIC KEY-----",
        bytes.fromhex(
            "0404112233445566778899aabbccddeeff"
            "112233445566778899aabbccddeeff"
            "112233445566778899aabbccddeeff"
            "112233445566778899aabbccddeeff1122"
        ),
    ]
    return private_key


@pytest.mark.usefixtures("current_request_with_host")
async def test_partner_login_auth_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key,
) -> None:
    """Test partner login auth errors abort the flow cleanly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi"
    ) as mock_api_class:
        mock_api = AsyncMock()
        mock_api.private_key = mock_private_key
        mock_api.get_private_key = AsyncMock()
        mock_api.partner_login = AsyncMock(side_effect=LoginRequired)
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
async def test_partner_login_partial_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key,
) -> None:
    """Test partner login succeeds when one region fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    public_key = (
        "0404112233445566778899aabbccddeeff"
        "112233445566778899aabbccddeeff"
        "112233445566778899aabbccddeeff"
        "112233445566778899aabbccddeeff1122"
    )

    mock_api_na = AsyncMock()
    mock_api_na.private_key = mock_private_key
    mock_api_na.get_private_key = AsyncMock()
    mock_api_na.partner_login = AsyncMock()
    mock_api_na.public_uncompressed_point = public_key
    mock_api_na.partner.register.return_value = {"response": {"public_key": public_key}}

    mock_api_eu = AsyncMock()
    mock_api_eu.private_key = mock_private_key
    mock_api_eu.get_private_key = AsyncMock()
    mock_api_eu.partner_login = AsyncMock(
        side_effect=TeslaFleetError("EU partner login failed")
    )

    with patch(
        "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi",
        side_effect=[mock_api_na, mock_api_eu],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "registration_complete"


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow_with_domain_registration(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test full flow with domain registration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    assert result["url"].startswith(AUTHORIZE_URL)
    parsed_url = urlparse(result["url"])
    parsed_query = parse_qs(parsed_url.query)
    assert parsed_query["response_type"][0] == "code"
    assert parsed_query["client_id"][0] == "user_client_id"
    assert parsed_query["redirect_uri"][0] == REDIRECT
    assert parsed_query["state"][0] == state
    assert parsed_query["prompt_missing_scopes"][0] == "true"
    assert parsed_query["scope"][0] == " ".join(SCOPES)
    assert "code_challenge" not in parsed_query

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch(
            "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi"
        ) as mock_api_class,
        patch(
            "homeassistant.components.tesla_fleet.async_setup_entry", return_value=True
        ),
    ):
        mock_api = _mock_api(mock_private_key)
        mock_api_class.return_value = mock_api

        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"

        # Enter domain - this should automatically register and go to
        # registration_complete
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "registration_complete"

        # Complete flow - provide user input to complete registration
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == UNIQUE_ID
    assert result["result"].unique_id == UNIQUE_ID


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_input_invalid_domain(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test domain input with invalid domain."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch(
            "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi"
        ) as mock_api_class,
    ):
        mock_api = _mock_api(
            mock_private_key,
            register_response={"response": {"public_key": PUBLIC_KEY}},
        )
        mock_api_class.return_value = mock_api

        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"

        # Enter invalid domain
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "invalid-domain"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"
        assert result["errors"] == {CONF_DOMAIN: "invalid_domain"}

        # Enter valid domain - this should automatically register and go to registration_complete
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "registration_complete"


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_invalid_response(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test an empty home region response returns to the domain step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch(
            "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi"
        ) as mock_api_class,
    ):
        mock_api = _mock_api(
            mock_private_key,
            register_response=None,
        )
        mock_api_class.return_value = mock_api

        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Enter domain - the home region returns nothing usable, so the flow
        # returns to the domain step instead of creating an entry
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"
        assert result["errors"] == {"base": "invalid_response"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_precondition_failed(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test PreconditionFailed on the home region maps to origin mismatch guidance."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch(
            "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi",
            side_effect=[
                _mock_api(
                    mock_private_key,
                    server="https://fleet-api.prd.na.vn.cloud.tesla.com",
                    register_side_effect=PreconditionFailed,
                ),
                _mock_api(
                    mock_private_key,
                    server="https://fleet-api.prd.eu.vn.cloud.tesla.com",
                    register_side_effect=PreconditionFailed,
                ),
            ],
        ),
    ):
        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Enter domain - the home region fails, returning to the domain step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"
        assert result["errors"] == {"base": "origin_mismatch"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_missing_public_key(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test a home region response without a public key returns to the domain step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch(
            "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi"
        ) as mock_api_class,
    ):
        mock_api = _mock_api(
            mock_private_key,
            public_key="test_point",
            register_response={"response": {}},
        )
        mock_api_class.return_value = mock_api

        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Enter domain - the home region returns no public key, so the flow
        # returns to the domain step instead of creating an entry
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"
        assert result["errors"] == {"base": "invalid_response"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_public_key_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test domain registration with public key mismatch."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch(
            "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi"
        ) as mock_api_class,
    ):
        mock_api = _mock_api(
            mock_private_key,
            public_key="expected_key",
            register_response={"response": {"public_key": "different_key"}},
        )
        mock_api_class.return_value = mock_api

        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Enter domain - this should fail and stay on domain_registration
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_registration"
        assert result["errors"] == {"base": "public_key_mismatch"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_partial_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test domain registration succeeds when one region fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch(
            "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi",
            side_effect=[
                _mock_api(
                    mock_private_key,
                    server="https://fleet-api.prd.na.vn.cloud.tesla.com",
                ),
                _mock_api(
                    mock_private_key,
                    server="https://fleet-api.prd.eu.vn.cloud.tesla.com",
                    register_side_effect=TeslaFleetError("EU registration failed"),
                ),
            ],
        ),
        patch(
            "homeassistant.components.tesla_fleet.async_setup_entry", return_value=True
        ),
    ):
        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"

        # Enter domain - the home region (NA) succeeds, EU fails, so acknowledge
        # the non-home region failure first
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "region_failures"
        assert result["description_placeholders"]["failed_regions"] == "Europe"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "registration_complete"

        # Complete flow
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == UNIQUE_ID


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_all_regions_fail(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test domain registration fails when all regions fail."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi",
        side_effect=[
            _mock_api(
                mock_private_key,
                public_key="test_point",
                server="https://fleet-api.prd.na.vn.cloud.tesla.com",
                register_side_effect=TeslaFleetError("NA registration failed"),
            ),
            _mock_api(
                mock_private_key,
                public_key="test_point",
                server="https://fleet-api.prd.eu.vn.cloud.tesla.com",
                register_side_effect=TeslaFleetError("EU registration failed"),
            ),
        ],
    ):
        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Enter domain - both regions fail, so return to the domain step with
        # the previously entered domain pre-filled
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"
        assert result["errors"] == {"base": "registration_failed"}
        assert (
            get_schema_suggested_value(result["data_schema"].schema, CONF_DOMAIN)
            == "example.com"
        )


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_failure_with_key_guidance(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test unclassified Tesla errors map to the generic registration guidance."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi",
        side_effect=[
            _mock_api(
                mock_private_key,
                public_key="test_point",
                server="https://fleet-api.prd.na.vn.cloud.tesla.com",
                register_side_effect=_tesla_error(
                    {"error": "public key must use secp256r1"}
                ),
            ),
            _mock_api(
                mock_private_key,
                public_key="test_point",
                server="https://fleet-api.prd.eu.vn.cloud.tesla.com",
                register_side_effect=_tesla_error(
                    {"error": "private_key does not match"}
                ),
            ),
        ],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "domain_input"
    assert result["errors"] == {"base": "registration_failed"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_failure_with_generic_guidance(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test unknown Tesla payloads map to the generic guidance."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi",
        side_effect=[
            _mock_api(
                mock_private_key,
                public_key="test_point",
                server="https://fleet-api.prd.na.vn.cloud.tesla.com",
                register_side_effect=_tesla_error({"error": "registration rejected"}),
            ),
            _mock_api(
                mock_private_key,
                public_key="test_point",
                server="https://fleet-api.prd.eu.vn.cloud.tesla.com",
                register_side_effect=_tesla_error({"error": "something else"}),
            ),
        ],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "domain_input"
    assert result["errors"] == {"base": "registration_failed"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_home_region_must_register(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test the flow cannot continue when only a non-home region registers.

    Commands are signed using the account's home region (NA), so a successful
    secondary region (EU) must not allow the flow to complete.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi",
        side_effect=[
            _mock_api(
                mock_private_key,
                server="https://fleet-api.prd.na.vn.cloud.tesla.com",
                register_side_effect=PreconditionFailed,
            ),
            _mock_api(
                mock_private_key,
                server="https://fleet-api.prd.eu.vn.cloud.tesla.com",
            ),
        ],
    ):
        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Enter domain - the home region (NA) fails while EU succeeds
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "domain_input"
    assert result["errors"] == {"base": "origin_mismatch"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_home_region_invalid_response(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test a malformed home region response does not create an entry.

    The home region (NA) returns a 200 with no usable payload while a secondary
    region (EU) succeeds. Commands are signed using the home region, so the flow
    must not validate the secondary region's key and complete setup.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi",
        side_effect=[
            _mock_api(
                mock_private_key,
                server="https://fleet-api.prd.na.vn.cloud.tesla.com",
                register_response=None,
            ),
            _mock_api(
                mock_private_key,
                server="https://fleet-api.prd.eu.vn.cloud.tesla.com",
            ),
        ],
    ):
        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Enter domain - the home region (NA) returns nothing usable while EU
        # succeeds, so the flow returns to the domain step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "domain_input"
    assert result["errors"] == {"base": "invalid_response"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_partner_login_home_region_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test the flow aborts when the home region's partner login fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    mock_api_na = _mock_api(
        mock_private_key, server="https://fleet-api.prd.na.vn.cloud.tesla.com"
    )
    mock_api_na.partner_login = AsyncMock(
        side_effect=TeslaFleetError("NA partner login failed")
    )
    mock_api_eu = _mock_api(
        mock_private_key, server="https://fleet-api.prd.eu.vn.cloud.tesla.com"
    )

    with patch(
        "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi",
        side_effect=[mock_api_na, mock_api_eu],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
async def test_partner_login_all_regions_fail(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key: Mock,
) -> None:
    """Test the flow aborts when partner login fails for every region."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    mock_api_na = _mock_api(
        mock_private_key, server="https://fleet-api.prd.na.vn.cloud.tesla.com"
    )
    mock_api_na.partner_login = AsyncMock(
        side_effect=TeslaFleetError("NA partner login failed")
    )
    mock_api_eu = _mock_api(
        mock_private_key, server="https://fleet-api.prd.eu.vn.cloud.tesla.com"
    )
    mock_api_eu.partner_login = AsyncMock(
        side_effect=TeslaFleetError("EU partner login failed")
    )

    with patch(
        "homeassistant.components.tesla_fleet.config_flow.TeslaFleetApi",
        side_effect=[mock_api_na, mock_api_eu],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
async def test_registration_complete_no_domain(
    hass: HomeAssistant,
) -> None:
    """Test registration complete step without domain."""

    flow_instance = OAuth2FlowHandler()
    flow_instance.hass = hass
    flow_instance.domain = None

    result = await flow_instance.async_step_registration_complete({})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "domain_input"


async def test_registration_complete_with_domain_and_user_input(
    hass: HomeAssistant,
) -> None:
    """Test registration complete step with domain and user input."""

    flow_instance = OAuth2FlowHandler()
    flow_instance.hass = hass
    flow_instance.domain = "example.com"
    flow_instance.uid = UNIQUE_ID
    flow_instance.data = {"token": {"access_token": "test"}}

    result = await flow_instance.async_step_registration_complete({"complete": True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == UNIQUE_ID


async def test_registration_complete_with_domain_no_user_input(
    hass: HomeAssistant,
) -> None:
    """Test registration complete step with domain but no user input."""

    flow_instance = OAuth2FlowHandler()
    flow_instance.hass = hass
    flow_instance.domain = "example.com"

    result = await flow_instance.async_step_registration_complete(None)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "registration_complete"
    assert (
        result["description_placeholders"]["virtual_key_url"]
        == "https://www.tesla.com/_ak/example.com"
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
) -> None:
    """Test Tesla Fleet reauthentication."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        version=1,
        data={},
    )
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.tesla_fleet.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
) -> None:
    """Test Tesla Fleet reauthentication with different account."""
    old_entry = MockConfigEntry(domain=DOMAIN, unique_id="baduid", version=1, data={})
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.tesla_fleet.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_account_mismatch"


@pytest.mark.usefixtures("current_request_with_host")
async def test_duplicate_unique_id_abort(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
) -> None:
    """Test duplicate unique ID aborts flow."""
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        version=1,
        data={},
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    # Complete OAuth - should abort due to duplicate unique_id
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_confirm_form(hass: HomeAssistant) -> None:
    """Test reauth confirm form display."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        version=1,
        data={},
    )
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {"name": "Tesla Fleet"}


@pytest.mark.parametrize(
    ("domain", "expected_valid"),
    [
        ("example.com", True),
        ("exa-mple.com", True),
        ("test.example.com", True),
        ("tes-t.example.com", True),
        ("sub.domain.example.org", True),
        ("su-b.dom-ain.exam-ple.org", True),
        ("https://example.com", False),
        ("invalid-domain", False),
        ("", False),
        ("example", False),
        ("example.", False),
        (".example.com", False),
        ("exam ple.com", False),
        ("-example.com", False),
        ("domain-.example.com", False),
    ],
)
def test_is_valid_domain(domain: str, expected_valid: bool) -> None:
    """Test domain validation."""

    assert OAuth2FlowHandler()._is_valid_domain(domain) == expected_valid


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        (PreconditionFailed(), "origin_mismatch"),
        (_tesla_error({"error": "allowed origin mismatch"}), "registration_failed"),
        (
            _tesla_error({"error": "public key must use secp256r1"}),
            "registration_failed",
        ),
        (_tesla_error({"error": "registration rejected"}), "registration_failed"),
    ],
    ids=["precondition", "origin_text", "public_key", "generic"],
)
def test_classify_region_registration_failure(
    err: TeslaFleetError, expected: str
) -> None:
    """Test registration failures are classified into translatable error keys."""

    assert OAuth2FlowHandler()._classify_region_registration_failure(err) == expected
