"""Tests for the Somfy config flow."""
from http import HTTPStatus
import logging
import time
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.network import NoURLAvailableError

from tests.common import MockConfigEntry, mock_platform
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

TEST_DOMAIN = "oauth2_test"
CLIENT_SECRET = "5678"
CLIENT_ID = "1234"
REFRESH_TOKEN = "mock-refresh-token"
ACCESS_TOKEN_1 = "mock-access-token-1"
ACCESS_TOKEN_2 = "mock-access-token-2"
AUTHORIZE_URL = "https://example.como/auth/authorize"
TOKEN_URL = "https://example.como/auth/token"


@pytest.fixture
async def local_impl(hass):
    """Local implementation."""
    assert await setup.async_setup_component(hass, "auth", {})
    return config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass, TEST_DOMAIN, CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL
    )


@pytest.fixture
def flow_handler(hass):
    """Return a registered config flow."""

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    class TestFlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler):
        """Test flow handler."""

        DOMAIN = TEST_DOMAIN

        @property
        def logger(self) -> logging.Logger:
            """Return logger."""
            return logging.getLogger(__name__)

        @property
        def extra_authorize_data(self) -> dict:
            """Extra data that needs to be appended to the authorize url."""
            return {"scope": "read write"}

    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestFlowHandler}):
        yield TestFlowHandler


class MockOAuth2Implementation(config_entry_oauth2_flow.AbstractOAuth2Implementation):
    """Mock implementation for testing."""

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Mock"

    @property
    def domain(self) -> str:
        """Domain that is providing the implementation."""
        return "test"

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"extra": "data"}

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize."""
        return "http://example.com/auth"

    async def async_resolve_external_data(self, external_data) -> dict:
        """Resolve external data to tokens."""
        return external_data

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh a token."""
        raise NotImplementedError()


def test_inherit_enforces_domain_set() -> None:
    """Test we enforce setting DOMAIN."""

    class TestFlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler):
        """Test flow handler."""

        @property
        def logger(self) -> logging.Logger:
            """Return logger."""
            return logging.getLogger(__name__)

    with patch.dict(
        config_entries.HANDLERS, {TEST_DOMAIN: TestFlowHandler}
    ), pytest.raises(TypeError):
        TestFlowHandler()


async def test_abort_if_no_implementation(hass: HomeAssistant, flow_handler) -> None:
    """Check flow abort when no implementations."""
    flow = flow_handler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "missing_configuration"


async def test_missing_credentials_for_domain(
    hass: HomeAssistant, flow_handler
) -> None:
    """Check flow abort for integration supporting application credentials."""
    flow = flow_handler()
    flow.hass = hass

    with patch("homeassistant.loader.APPLICATION_CREDENTIALS", [TEST_DOMAIN]):
        result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


async def test_abort_if_authorization_timeout(
    hass: HomeAssistant, flow_handler, local_impl, current_request_with_host: None
) -> None:
    """Check timeout generating authorization url."""
    flow_handler.async_register_implementation(hass, local_impl)

    flow = flow_handler()
    flow.hass = hass

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.asyncio.timeout",
        side_effect=TimeoutError,
    ):
        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "authorize_url_timeout"


async def test_abort_if_no_url_available(
    hass: HomeAssistant, flow_handler, local_impl, current_request_with_host: None
) -> None:
    """Check no_url_available generating authorization url."""
    flow_handler.async_register_implementation(hass, local_impl)

    flow = flow_handler()
    flow.hass = hass

    with patch.object(
        local_impl, "async_generate_authorize_url", side_effect=NoURLAvailableError
    ):
        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_url_available"


@pytest.mark.parametrize("expires_in_dict", [{}, {"expires_in": "badnumber"}])
async def test_abort_if_oauth_error(
    hass: HomeAssistant,
    flow_handler,
    local_impl,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    expires_in_dict: dict[str, str],
) -> None:
    """Check bad oauth token."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"

    # Pick implementation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"implementation": TEST_DOMAIN}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{AUTHORIZE_URL}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=read+write"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": REFRESH_TOKEN,
            "access_token": ACCESS_TOKEN_1,
            "type": "bearer",
        }
        | expires_in_dict,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


async def test_abort_if_oauth_rejected(
    hass: HomeAssistant,
    flow_handler,
    local_impl,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> None:
    """Check bad oauth token."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"

    # Pick implementation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"implementation": TEST_DOMAIN}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{AUTHORIZE_URL}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=read+write"
    )

    client = await hass_client_no_auth()
    resp = await client.get(
        f"/auth/external/callback?error=access_denied&state={state}"
    )
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "user_rejected_authorize"
    assert result["description_placeholders"] == {"error": "access_denied"}


async def test_abort_on_oauth_timeout_error(
    hass: HomeAssistant,
    flow_handler,
    local_impl,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> None:
    """Check timeout during oauth token exchange."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"

    # Pick implementation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"implementation": TEST_DOMAIN}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{AUTHORIZE_URL}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=read+write"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.asyncio.timeout",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "oauth_timeout"


async def test_step_discovery(hass: HomeAssistant, flow_handler, local_impl) -> None:
    """Check flow triggers from discovery."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=data_entry_flow.BaseServiceInfo(),
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"


async def test_abort_discovered_multiple(
    hass: HomeAssistant, flow_handler, local_impl
) -> None:
    """Test if aborts when discovered multiple times."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=data_entry_flow.BaseServiceInfo(),
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=data_entry_flow.BaseServiceInfo(),
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    ("status_code", "error_body", "error_reason", "error_log"),
    [
        (
            HTTPStatus.UNAUTHORIZED,
            {},
            "oauth_unauthorized",
            "Token request for oauth2_test failed (unknown): unknown",
        ),
        (
            HTTPStatus.NOT_FOUND,
            {},
            "oauth_failed",
            "Token request for oauth2_test failed (unknown): unknown",
        ),
        (
            HTTPStatus.INTERNAL_SERVER_ERROR,
            {},
            "oauth_failed",
            "Token request for oauth2_test failed (unknown): unknown",
        ),
        (
            HTTPStatus.BAD_REQUEST,
            {
                "error": "invalid_request",
                "error_description": "Request was missing the 'redirect_uri' parameter.",
                "error_uri": "See the full API docs at https://authorization-server.com/docs/access_token",
            },
            "oauth_failed",
            "Token request for oauth2_test failed (invalid_request): Request was missing the",
        ),
    ],
)
async def test_abort_if_oauth_token_error(
    hass: HomeAssistant,
    flow_handler,
    local_impl,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    status_code: HTTPStatus,
    error_body: dict[str, Any],
    error_reason: str,
    error_log: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Check error when obtaining an oauth token."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"

    # Pick implementation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"implementation": TEST_DOMAIN}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{AUTHORIZE_URL}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=read+write"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        TOKEN_URL,
        status=status_code,
        json=error_body,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == error_reason
    assert error_log in caplog.text


async def test_abort_if_oauth_token_closing_error(
    hass: HomeAssistant,
    flow_handler,
    local_impl,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Check error when obtaining an oauth token."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"

    # Pick implementation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"implementation": TEST_DOMAIN}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{AUTHORIZE_URL}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=read+write"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        TOKEN_URL,
        status=HTTPStatus.UNAUTHORIZED,
        closing=True,
    )

    with caplog.at_level(logging.DEBUG):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert "Token request for oauth2_test failed (unknown): unknown" in caplog.text

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "oauth_unauthorized"


async def test_abort_discovered_existing_entries(
    hass: HomeAssistant, flow_handler, local_impl
) -> None:
    """Test if abort discovery when entries exists."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=data_entry_flow.BaseServiceInfo(),
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_flow(
    hass: HomeAssistant,
    flow_handler,
    local_impl,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> None:
    """Check full flow."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"

    # Pick implementation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"implementation": TEST_DOMAIN}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{AUTHORIZE_URL}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=read+write"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": REFRESH_TOKEN,
            "access_token": ACCESS_TOKEN_1,
            "type": "bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["data"]["auth_implementation"] == TEST_DOMAIN

    result["data"]["token"].pop("expires_at")
    assert result["data"]["token"] == {
        "refresh_token": REFRESH_TOKEN,
        "access_token": ACCESS_TOKEN_1,
        "type": "bearer",
        "expires_in": 60,
    }

    entry = hass.config_entries.async_entries(TEST_DOMAIN)[0]

    assert (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
        is local_impl
    )


async def test_local_refresh_token(
    hass: HomeAssistant, local_impl, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we can refresh token."""
    aioclient_mock.post(
        TOKEN_URL, json={"access_token": ACCESS_TOKEN_2, "expires_in": 100}
    )

    new_tokens = await local_impl.async_refresh_token(
        {
            "refresh_token": REFRESH_TOKEN,
            "access_token": ACCESS_TOKEN_1,
            "type": "bearer",
            "expires_in": 60,
        }
    )
    new_tokens.pop("expires_at")

    assert new_tokens == {
        "refresh_token": REFRESH_TOKEN,
        "access_token": ACCESS_TOKEN_2,
        "type": "bearer",
        "expires_in": 100,
    }

    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
    }


async def test_oauth_session(
    hass: HomeAssistant, flow_handler, local_impl, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the OAuth2 session helper."""
    flow_handler.async_register_implementation(hass, local_impl)

    aioclient_mock.post(
        TOKEN_URL, json={"access_token": ACCESS_TOKEN_2, "expires_in": 100}
    )

    aioclient_mock.post("https://example.com", status=201)

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                "expires_in": 10,
                "expires_at": 0,  # Forces a refresh,
                "token_type": "bearer",
                "random_other_data": "should_stay",
            },
        },
    )

    now = time.time()
    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    resp = await session.async_request("post", "https://example.com")
    assert resp.status == 201

    # Refresh token, make request
    assert len(aioclient_mock.mock_calls) == 2

    assert (
        aioclient_mock.mock_calls[1][3]["authorization"] == f"Bearer {ACCESS_TOKEN_2}"
    )

    assert config_entry.data["token"]["refresh_token"] == REFRESH_TOKEN
    assert config_entry.data["token"]["access_token"] == ACCESS_TOKEN_2
    assert config_entry.data["token"]["expires_in"] == 100
    assert config_entry.data["token"]["random_other_data"] == "should_stay"
    assert round(config_entry.data["token"]["expires_at"] - now) == 100


async def test_oauth_session_with_clock_slightly_out_of_sync(
    hass: HomeAssistant, flow_handler, local_impl, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the OAuth2 session helper when the remote clock is slightly out of sync."""
    flow_handler.async_register_implementation(hass, local_impl)

    aioclient_mock.post(
        TOKEN_URL, json={"access_token": ACCESS_TOKEN_2, "expires_in": 19}
    )

    aioclient_mock.post("https://example.com", status=201)

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                "expires_in": 19,
                "expires_at": time.time() + 19,  # Forces a refresh,
                "token_type": "bearer",
                "random_other_data": "should_stay",
            },
        },
    )

    now = time.time()
    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    resp = await session.async_request("post", "https://example.com")
    assert resp.status == 201

    # Refresh token, make request
    assert len(aioclient_mock.mock_calls) == 2

    assert (
        aioclient_mock.mock_calls[1][3]["authorization"] == f"Bearer {ACCESS_TOKEN_2}"
    )

    assert config_entry.data["token"]["refresh_token"] == REFRESH_TOKEN
    assert config_entry.data["token"]["access_token"] == ACCESS_TOKEN_2
    assert config_entry.data["token"]["expires_in"] == 19
    assert config_entry.data["token"]["random_other_data"] == "should_stay"
    assert round(config_entry.data["token"]["expires_at"] - now) == 19


async def test_oauth_session_no_token_refresh_needed(
    hass: HomeAssistant, flow_handler, local_impl, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the OAuth2 session helper when no refresh is needed."""
    flow_handler.async_register_implementation(hass, local_impl)

    aioclient_mock.post("https://example.com", status=201)

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                "expires_in": 500,
                "expires_at": time.time() + 500,  # Should NOT refresh
                "token_type": "bearer",
                "random_other_data": "should_stay",
            },
        },
    )

    now = time.time()
    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    resp = await session.async_request("post", "https://example.com")
    assert resp.status == 201

    # make request (no refresh)
    assert len(aioclient_mock.mock_calls) == 1

    assert (
        aioclient_mock.mock_calls[0][3]["authorization"] == f"Bearer {ACCESS_TOKEN_1}"
    )

    assert config_entry.data["token"]["refresh_token"] == REFRESH_TOKEN
    assert config_entry.data["token"]["access_token"] == ACCESS_TOKEN_1
    assert config_entry.data["token"]["expires_in"] == 500
    assert config_entry.data["token"]["random_other_data"] == "should_stay"
    assert round(config_entry.data["token"]["expires_at"] - now) == 500


async def test_implementation_provider(hass: HomeAssistant, local_impl) -> None:
    """Test providing an implementation provider."""
    assert (
        await config_entry_oauth2_flow.async_get_implementations(hass, TEST_DOMAIN)
        == {}
    )

    mock_domain_with_impl = "some_domain"

    config_entry_oauth2_flow.async_register_implementation(
        hass, mock_domain_with_impl, local_impl
    )

    assert await config_entry_oauth2_flow.async_get_implementations(
        hass, mock_domain_with_impl
    ) == {TEST_DOMAIN: local_impl}

    provider_source = []

    async def async_provide_implementation(hass, domain):
        """Mock implementation provider."""
        return provider_source

    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, "cloud", async_provide_implementation
    )

    assert await config_entry_oauth2_flow.async_get_implementations(
        hass, mock_domain_with_impl
    ) == {TEST_DOMAIN: local_impl}

    provider_source.append(
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass, "cloud", CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL
        )
    )

    assert await config_entry_oauth2_flow.async_get_implementations(
        hass, mock_domain_with_impl
    ) == {TEST_DOMAIN: local_impl, "cloud": provider_source[0]}

    provider_source.append(
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass, "other", CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL
        )
    )

    assert await config_entry_oauth2_flow.async_get_implementations(
        hass, mock_domain_with_impl
    ) == {
        TEST_DOMAIN: local_impl,
        "cloud": provider_source[0],
        "other": provider_source[1],
    }


async def test_oauth_session_refresh_failure(
    hass: HomeAssistant, flow_handler, local_impl, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the OAuth2 session helper when no refresh is needed."""
    flow_handler.async_register_implementation(hass, local_impl)

    aioclient_mock.post(TOKEN_URL, status=400)

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                # Already expired, requires a refresh
                "expires_in": -500,
                "expires_at": time.time() - 500,
                "token_type": "bearer",
                "random_other_data": "should_stay",
            },
        },
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    with pytest.raises(aiohttp.client_exceptions.ClientResponseError):
        await session.async_request("post", "https://example.com")


async def test_oauth2_without_secret_init(
    local_impl, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Check authorize callback without secret initalizated."""
    client = await hass_client_no_auth()
    resp = await client.get("/auth/external/callback?code=abcd&state=qwer")
    assert resp.status == 400
