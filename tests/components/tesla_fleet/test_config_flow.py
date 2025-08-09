"""Test the Tesla Fleet config flow."""

from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from tesla_fleet_api.exceptions import (
    InvalidResponse,
    PreconditionFailed,
    TeslaFleetError,
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.tesla_fleet.config_flow import OAuth2FlowHandler
from homeassistant.components.tesla_fleet.const import (
    AUTHORIZE_URL,
    CONF_DOMAIN,
    DOMAIN,
    SCOPES,
    TOKEN_URL,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT = "https://example.com/auth/external/callback"
UNIQUE_ID = "uid"


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
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("user_client_id", "user_client_secret"),
        "user_cred",
    )


@pytest.fixture
def mock_private_key():
    """Mock private key for testing."""
    private_key = Mock()
    public_key = Mock()
    private_key.public_key.return_value = public_key
    public_key.public_bytes.side_effect = [
        b"-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----",
        bytes.fromhex(
            "0404112233445566778899aabbccddeeff112233445566778899aabbccddeeff112233445566778899aabbccddeeff112233445566778899aabbccddeeff1122"
        ),
    ]
    return private_key


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow_with_domain_registration(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key,
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
        mock_api = AsyncMock()
        mock_api.private_key = mock_private_key
        mock_api.get_private_key = AsyncMock()
        mock_api.partner_login = AsyncMock()
        mock_api.public_uncompressed_point = "0404112233445566778899aabbccddeeff112233445566778899aabbccddeeff112233445566778899aabbccddeeff112233445566778899aabbccddeeff1122"
        mock_api.partner.register.return_value = {
            "response": {
                "public_key": "0404112233445566778899aabbccddeeff112233445566778899aabbccddeeff112233445566778899aabbccddeeff112233445566778899aabbccddeeff1122"
            }
        }
        mock_api_class.return_value = mock_api

        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"

        # Enter domain - this should automatically register and go to registration_complete
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
    mock_private_key,
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
        mock_api = AsyncMock()
        mock_api.private_key = mock_private_key
        mock_api.get_private_key = AsyncMock()
        mock_api.partner_login = AsyncMock()
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
        mock_api.public_uncompressed_point = "0404112233445566778899aabbccddeeff112233445566778899aabbccddeeff112233445566778899aabbccddeeff112233445566778899aabbccddeeff1122"
        mock_api.partner.register.return_value = {
            "response": {
                "public_key": "0404112233445566778899aabbccddeeff112233445566778899aabbccddeeff112233445566778899aabbccddeeff112233445566778899aabbccddeeff1122"
            }
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "registration_complete"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (InvalidResponse, "invalid_response"),
        (TeslaFleetError("Custom error"), "unknown_error"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_errors(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key,
    side_effect,
    expected_error,
) -> None:
    """Test domain registration with errors that stay on domain_registration step."""
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
        mock_api = AsyncMock()
        mock_api.private_key = mock_private_key
        mock_api.get_private_key = AsyncMock()
        mock_api.partner_login = AsyncMock()
        mock_api.public_uncompressed_point = "test_point"
        mock_api.partner.register.side_effect = side_effect
        mock_api_class.return_value = mock_api

        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Enter domain - this should fail and stay on domain_registration
        with patch(
            "homeassistant.helpers.translation.async_get_translations", return_value={}
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_DOMAIN: "example.com"}
            )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_registration"
        assert result["errors"] == {"base": expected_error}


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_precondition_failed(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key,
) -> None:
    """Test domain registration with PreconditionFailed redirects to domain_input."""
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
        mock_api = AsyncMock()
        mock_api.private_key = mock_private_key
        mock_api.get_private_key = AsyncMock()
        mock_api.partner_login = AsyncMock()
        mock_api.public_uncompressed_point = "test_point"
        mock_api.partner.register.side_effect = PreconditionFailed
        mock_api_class.return_value = mock_api

        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Enter domain - this should go to domain_registration and then fail back to domain_input
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_input"
        assert result["errors"] == {CONF_DOMAIN: "precondition_failed"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_public_key_not_found(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key,
) -> None:
    """Test domain registration with missing public key."""
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
        mock_api = AsyncMock()
        mock_api.private_key = mock_private_key
        mock_api.get_private_key = AsyncMock()
        mock_api.partner_login = AsyncMock()
        mock_api.public_uncompressed_point = "test_point"
        mock_api.partner.register.return_value = {"response": {}}
        mock_api_class.return_value = mock_api

        # Complete OAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Enter domain - this should fail and stay on domain_registration
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DOMAIN: "example.com"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "domain_registration"
        assert result["errors"] == {"base": "public_key_not_found"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_domain_registration_public_key_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    mock_private_key,
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
        mock_api = AsyncMock()
        mock_api.private_key = mock_private_key
        mock_api.get_private_key = AsyncMock()
        mock_api.partner_login = AsyncMock()
        mock_api.public_uncompressed_point = "expected_key"
        mock_api.partner.register.return_value = {
            "response": {"public_key": "different_key"}
        }
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
