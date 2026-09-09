"""Tests for the Somfy config flow."""

from collections.abc import AsyncGenerator, Generator
from http import HTTPStatus
import logging
import time
from typing import Any
from unittest.mock import AsyncMock, patch

from aiohttp import (
    ClientError,
    ClientPayloadError,
    ClientResponseError,
    ContentTypeError,
    RequestInfo,
    ServerTimeoutError,
)
from multidict import CIMultiDict, CIMultiDictProxy
import pytest
from yarl import URL

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.network import NoURLAvailableError

from tests.common import MockConfigEntry, MockModule, mock_integration, mock_platform
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse
from tests.typing import ClientSessionGenerator

TEST_DOMAIN = "oauth2_test"
CLIENT_SECRET = "5678"
CLIENT_ID = "1234"
REFRESH_TOKEN = "mock-refresh-token"
ACCESS_TOKEN_1 = "mock-access-token-1"
ACCESS_TOKEN_2 = "mock-access-token-2"
AUTHORIZE_URL = "https://example.como/auth/authorize"
TOKEN_URL = "https://example.como/auth/token"
# Far enough ahead that a token carrying it always counts as unexpired.
FUTURE_EXPIRES_AT = 2000000000
MOCK_SECRET_TOKEN_URLSAFE = (
    "token-"
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
)


@pytest.fixture
async def local_impl(
    hass: HomeAssistant,
) -> config_entry_oauth2_flow.LocalOAuth2Implementation:
    """Local implementation."""
    assert await setup.async_setup_component(hass, "auth", {})
    return config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass, TEST_DOMAIN, CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL
    )


@pytest.fixture
async def local_impl_pkce(
    hass: HomeAssistant,
) -> AsyncGenerator[config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce]:
    """Local implementation."""
    assert await setup.async_setup_component(hass, "auth", {})
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.secrets.token_urlsafe",
        return_value=MOCK_SECRET_TOKEN_URLSAFE
        + "bbbbbb",  # Add some characters that should be removed by the logic.
    ):
        yield config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce(
            hass, TEST_DOMAIN, CLIENT_ID, AUTHORIZE_URL, TOKEN_URL
        )


@pytest.fixture
def flow_handler(
    hass: HomeAssistant,
) -> Generator[type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler]]:
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
        raise NotImplementedError


def test_inherit_enforces_domain_set() -> None:
    """Test we enforce setting DOMAIN."""

    class TestFlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler):
        """Test flow handler."""

        @property
        def logger(self) -> logging.Logger:
            """Return logger."""
            return logging.getLogger(__name__)

    with (
        patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestFlowHandler}),
        pytest.raises(TypeError),
    ):
        TestFlowHandler()


async def test_abort_if_no_implementation(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
) -> None:
    """Check flow abort when no implementations."""
    flow = flow_handler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "missing_configuration"
    # Not a shared reason, so it stays with the integration owning the flow
    assert "translation_domain" not in result


async def test_abort_if_oauth_implementation_unavailable(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
) -> None:
    """Check flow abort when implementation is unavailable."""

    async def mock_provider(
        hass: HomeAssistant, domain: str
    ) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
        raise config_entry_oauth2_flow.ImplementationUnavailableError("Test error")

    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, "test_provider", mock_provider
    )

    flow = flow_handler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "oauth_implementation_unavailable"
    assert result["translation_domain"] == HOMEASSISTANT_DOMAIN


@pytest.mark.parametrize(
    "reason",
    [
        "authorize_url_timeout",
        "missing_credentials",
        "no_url_available",
        "oauth_error",
        "oauth_failed",
        "oauth_implementation_unavailable",
        "oauth_timeout",
        "oauth_unauthorized",
        "user_rejected_authorize",
    ],
)
async def test_shared_abort_reasons_use_homeassistant_domain(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    reason: str,
) -> None:
    """Test shared abort reasons are translated by the homeassistant domain."""
    flow = flow_handler()
    flow.hass = hass
    flow.flow_id = "test-flow-id"
    flow.handler = TEST_DOMAIN

    result = flow.async_abort(reason=reason)

    assert result["reason"] == reason
    assert result["translation_domain"] == HOMEASSISTANT_DOMAIN


async def test_abort_reason_translation_domain_not_overridden(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
) -> None:
    """Test an explicit domain wins and unknown reasons stay untranslated."""
    flow = flow_handler()
    flow.hass = hass
    flow.flow_id = "test-flow-id"
    flow.handler = TEST_DOMAIN

    explicit = flow.async_abort(reason="oauth_error", translation_domain="other_domain")
    assert explicit["translation_domain"] == "other_domain"

    not_shared = flow.async_abort(reason="some_integration_reason")
    assert "translation_domain" not in not_shared


async def test_missing_credentials_for_domain(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
) -> None:
    """Check flow abort for integration supporting application credentials."""
    flow = flow_handler()
    flow.hass = hass

    with patch("homeassistant.loader.APPLICATION_CREDENTIALS", [TEST_DOMAIN]):
        result = await flow.async_step_user()
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("current_request_with_host")
async def test_abort_if_authorization_timeout(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
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

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "authorize_url_timeout"


@pytest.mark.usefixtures("current_request_with_host")
async def test_abort_if_no_url_available(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
) -> None:
    """Check no_url_available generating authorization url."""
    flow_handler.async_register_implementation(hass, local_impl)

    flow = flow_handler()
    flow.hass = hass

    with patch.object(
        local_impl, "async_generate_authorize_url", side_effect=NoURLAvailableError
    ):
        result = await flow.async_step_user()

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_url_available"


@pytest.mark.parametrize("expires_in_dict", [{}, {"expires_in": "badnumber"}])
@pytest.mark.usefixtures("current_request_with_host")
async def test_abort_if_oauth_error(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
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

    assert result["type"] is data_entry_flow.FlowResultType.FORM
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

    assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP
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

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
async def test_abort_if_oauth_rejected(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check bad oauth token."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
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

    assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP
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

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "user_rejected_authorize"
    assert result["description_placeholders"] == {"error": "access_denied"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_abort_on_oauth_timeout_error(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check timeout during oauth token exchange."""
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
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

    assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP
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

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "oauth_timeout"


async def test_step_discovery(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
) -> None:
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

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "oauth_discovery"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"


async def test_abort_discovered_multiple(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=data_entry_flow.BaseServiceInfo(),
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    ("status_code", "error_body", "error_reason", "expected_detail"),
    [
        (HTTPStatus.UNAUTHORIZED, {}, "oauth_unauthorized", "unknown error"),
        (HTTPStatus.NOT_FOUND, {}, "oauth_unauthorized", "unknown error"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, {}, "oauth_failed", "unknown error"),
        (
            HTTPStatus.UNAUTHORIZED,
            {"error_description": "The token has expired."},
            "oauth_unauthorized",
            "unknown error: The token has expired.",
        ),
        (
            HTTPStatus.BAD_REQUEST,
            {
                "error": "invalid_request",
                "error_description": (
                    "Request was missing the 'redirect_uri' parameter."
                ),
                "error_uri": "Sensible URI: https://authorization-server.com/docs/access_token",
            },
            "oauth_unauthorized",
            "invalid_request: Request was missing the 'redirect_uri' parameter.",
        ),
        (
            HTTPStatus.BAD_REQUEST,
            "some error which is not formatted",
            "oauth_unauthorized",
            '"some error which is not formatted"',
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_abort_if_oauth_token_error(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    status_code: HTTPStatus,
    error_body: dict[str, Any],
    error_reason: str,
    expected_detail: str,
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

    assert result["type"] is data_entry_flow.FlowResultType.FORM
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

    assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP
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

    with caplog.at_level(logging.DEBUG):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert (
        f"Token request for {TEST_DOMAIN} failed ({status_code}): {expected_detail}"
        in caplog.text
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == error_reason


@pytest.mark.usefixtures("current_request_with_host")
async def test_abort_if_oauth_token_closing_error(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
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

    assert result["type"] is data_entry_flow.FlowResultType.FORM
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

    assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP
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
    assert "Token request for oauth2_test failed (401): unknown" in caplog.text

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "oauth_unauthorized"


async def test_abort_discovered_existing_entries(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
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

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("additional_components", "expected_redirect_uri"),
    [
        ([], "https://example.com/auth/external/callback"),
        (["my"], "https://my.home-assistant.io/redirect/oauth"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    additional_components: list[str],
    expected_redirect_uri: str,
) -> None:
    """Check full flow."""
    for component in additional_components:
        assert await setup.async_setup_component(hass, component, {})
    flow_handler.async_register_implementation(hass, local_impl)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, MockOAuth2Implementation()
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"

    # Pick implementation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"implementation": TEST_DOMAIN}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": expected_redirect_uri,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{AUTHORIZE_URL}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={expected_redirect_uri}"
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
    hass: HomeAssistant,
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
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
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
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
    config_entry.add_to_hass(hass)

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
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
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
    config_entry.add_to_hass(hass)

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
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
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

    async def async_provide_implementation(
        hass: HomeAssistant, domain: str
    ) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
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


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        (
            HTTPStatus.BAD_REQUEST,
            OAuth2TokenRequestReauthError,
        ),
        (
            HTTPStatus.TOO_MANY_REQUESTS,  # 429, odd one, but treated as transient
            OAuth2TokenRequestTransientError,
        ),
        (
            HTTPStatus.INTERNAL_SERVER_ERROR,  # 500 range, so treated as transient
            OAuth2TokenRequestTransientError,
        ),
        (
            600,  # Nonsense code, just to hit the generic error branch
            OAuth2TokenRequestError,
        ),
    ],
)
async def test_oauth_session_refresh_failure_exceptions(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
    status_code: int,
    expected_exception: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test OAuth2 session refresh failures raise mapped exceptions."""
    mock_integration(hass, MockModule(domain=TEST_DOMAIN))

    flow_handler.async_register_implementation(hass, local_impl)

    aioclient_mock.post(TOKEN_URL, status=status_code, json={})

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
    config_entry.add_to_hass(hass)

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(expected_exception) as err,
    ):
        await session.async_request("post", "https://example.com")

    assert err.value.status == status_code
    assert f"Token request for {TEST_DOMAIN} failed" in caplog.text


@pytest.mark.parametrize(
    "raised",
    [
        pytest.param(ClientError("Cannot connect"), id="client_error"),
        pytest.param(ServerTimeoutError("Timeout"), id="timeout"),
    ],
)
async def test_oauth_session_refresh_connection_error_is_transient(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
    raised: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a token request that never gets a response is mapped to a transient error."""
    mock_integration(hass, MockModule(domain=TEST_DOMAIN))

    flow_handler.async_register_implementation(hass, local_impl)

    aioclient_mock.post(TOKEN_URL, exc=raised)

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(OAuth2TokenRequestConnectionError) as err,
    ):
        await session.async_ensure_token_valid()

    # Integrations rely on this to retry setup without mapping the error themselves.
    assert isinstance(err.value, ConfigEntryNotReady)
    assert err.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert err.value.translation_key == "oauth2_helper_refresh_transient"
    assert f"Token request for {TEST_DOMAIN} got no response" in caplog.text
    assert str(raised) in caplog.text


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"access_token": ACCESS_TOKEN_2}, id="missing_expires_in"),
        pytest.param(
            {"access_token": ACCESS_TOKEN_2, "expires_in": "soon"},
            id="unparsable_expires_in",
        ),
        pytest.param(
            {"access_token": ACCESS_TOKEN_2, "expires_in": None},
            id="null_expires_in",
        ),
    ],
)
async def test_oauth_session_malformed_refresh_response_is_not_reauth(
    hass: HomeAssistant,
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
) -> None:
    """Test an unusable token response retries instead of blaming stored credentials."""
    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "access_token": ACCESS_TOKEN_1,
                "refresh_token": REFRESH_TOKEN,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)

    aioclient_mock.post(TOKEN_URL, json=response)

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    with (
        patch.object(config_entry, "async_start_reauth_if_available") as start_reauth,
        pytest.raises(OAuth2TokenRequestConnectionError) as err,
    ):
        await session.async_ensure_token_valid()

    assert isinstance(err.value, ConfigEntryNotReady)
    assert err.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert err.value.translation_key == "oauth2_helper_refresh_transient"
    # Relinking the account cannot fix a bad response, so it must not ask for it.
    start_reauth.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"expires_in": 100}, id="no_access_token"),
        pytest.param({"access_token": None, "expires_in": 100}, id="null_access_token"),
        pytest.param({"access_token": "", "expires_in": 100}, id="blank_access_token"),
    ],
)
async def test_oauth_session_refresh_without_access_token_is_rejected(
    hass: HomeAssistant,
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
) -> None:
    """Test a response with no usable access token is not merged over the old one."""
    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "access_token": ACCESS_TOKEN_1,
                "refresh_token": REFRESH_TOKEN,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)

    aioclient_mock.post(TOKEN_URL, json=response)

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    with pytest.raises(OAuth2TokenRequestConnectionError):
        await session.async_ensure_token_valid()

    # The stale token must stay expired so the next attempt refreshes again.
    assert config_entry.data["token"]["access_token"] == ACCESS_TOKEN_1
    assert config_entry.data["token"]["expires_at"] == 0


@pytest.mark.parametrize(
    "refreshed",
    [
        pytest.param({"expires_in": 100}, id="no_access_token"),
        pytest.param({"access_token": None, "expires_in": 100}, id="null_access_token"),
    ],
)
async def test_oauth_session_custom_implementation_without_access_token(
    hass: HomeAssistant,
    refreshed: dict[str, Any],
) -> None:
    """Test an implementation returning no usable access token is rejected."""

    class BadImplementation(MockOAuth2Implementation):
        """Implementation whose refresh skips the local token request."""

        async def _async_refresh_token(self, token: dict) -> dict:
            """Refresh a token."""
            return refreshed

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "access_token": ACCESS_TOKEN_1,
                "refresh_token": REFRESH_TOKEN,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)

    session = config_entry_oauth2_flow.OAuth2Session(
        hass, config_entry, BadImplementation()
    )
    with pytest.raises(OAuth2TokenRequestConnectionError):
        await session.async_ensure_token_valid()

    assert config_entry.data["token"]["access_token"] == ACCESS_TOKEN_1


@pytest.mark.parametrize(
    "refreshed",
    [
        pytest.param({"expires_at": FUTURE_EXPIRES_AT}, id="no_access_token"),
        pytest.param({"access_token": ACCESS_TOKEN_2}, id="no_expires_at"),
    ],
)
async def test_oauth_session_never_stores_an_unusable_token(
    hass: HomeAssistant,
    refreshed: dict[str, Any],
) -> None:
    """Test the session checks the new token even when the refresh skips its own."""

    class UncheckedImplementation(MockOAuth2Implementation):
        """Implementation overriding the public refresh, so nothing maps for it."""

        async def async_refresh_token(self, token: dict) -> dict:
            """Refresh a token without the base class validation."""
            return refreshed

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "access_token": ACCESS_TOKEN_1,
                "refresh_token": REFRESH_TOKEN,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)

    session = config_entry_oauth2_flow.OAuth2Session(
        hass, config_entry, UncheckedImplementation()
    )
    with pytest.raises(OAuth2TokenRequestConnectionError):
        await session.async_ensure_token_valid()

    assert config_entry.data["token"]["access_token"] == ACCESS_TOKEN_1
    assert config_entry.data["token"]["expires_at"] == 0


@pytest.mark.parametrize(
    ("raised", "expected_exception"),
    [
        pytest.param(
            ClientPayloadError("Disconnected"),
            OAuth2TokenRequestConnectionError,
            id="payload_error",
        ),
        pytest.param(
            ContentTypeError(
                RequestInfo(
                    url=URL(TOKEN_URL),
                    method="POST",
                    headers=CIMultiDictProxy(CIMultiDict()),
                ),
                (),
            ),
            OAuth2TokenRequestError,
            id="content_type_error",
        ),
    ],
)
async def test_oauth_session_refresh_body_error_is_mapped(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
    raised: Exception,
    expected_exception: type[Exception],
) -> None:
    """Test a failure reading the token response body does not leak an aiohttp error."""
    mock_integration(hass, MockModule(domain=TEST_DOMAIN))

    flow_handler.async_register_implementation(hass, local_impl)

    aioclient_mock.post(TOKEN_URL, json={})

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    with (
        patch.object(AiohttpClientMockResponse, "json", side_effect=raised),
        pytest.raises(expected_exception) as err,
    ):
        await session.async_ensure_token_valid()

    assert type(err.value) is expected_exception
    assert isinstance(err.value, ConfigEntryNotReady)


@pytest.mark.parametrize(
    ("raised", "expected_exception", "expected_base"),
    [
        pytest.param(
            ClientResponseError(
                RequestInfo(
                    url=URL(TOKEN_URL),
                    method="POST",
                    headers=CIMultiDictProxy(CIMultiDict()),
                ),
                (),
                status=HTTPStatus.UNAUTHORIZED,
            ),
            OAuth2TokenRequestReauthError,
            ConfigEntryAuthFailed,
            id="reauth",
        ),
        pytest.param(
            ClientResponseError(
                RequestInfo(
                    url=URL(TOKEN_URL),
                    method="POST",
                    headers=CIMultiDictProxy(CIMultiDict()),
                ),
                (),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            ),
            OAuth2TokenRequestTransientError,
            ConfigEntryNotReady,
            id="transient",
        ),
        pytest.param(
            ClientError("Cannot connect"),
            OAuth2TokenRequestConnectionError,
            ConfigEntryNotReady,
            id="connection_error",
        ),
    ],
)
async def test_refresh_maps_errors_from_custom_implementation(
    hass: HomeAssistant,
    raised: Exception,
    expected_exception: type[Exception],
    expected_base: type[Exception],
) -> None:
    """Test an implementation issuing its own token request still raises mapped errors."""

    class UnmappedImplementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
        """Implementation that lets raw aiohttp errors escape, like a custom one."""

        async def _async_refresh_token(self, token: dict) -> dict:
            raise raised

    implementation = UnmappedImplementation(
        hass, TEST_DOMAIN, CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL
    )

    with pytest.raises(expected_exception) as err:
        await implementation.async_refresh_token({"refresh_token": REFRESH_TOKEN})

    assert type(err.value) is expected_exception
    assert isinstance(err.value, expected_base)
    assert err.value.__cause__ is raised


@pytest.mark.parametrize(
    "entry_state",
    [
        pytest.param(
            config_entries.ConfigEntryState.SETUP_IN_PROGRESS, id="during_setup"
        ),
        pytest.param(config_entries.ConfigEntryState.LOADED, id="after_setup"),
    ],
)
async def test_oauth_session_reauth_error_starts_reauth(
    hass: HomeAssistant,
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
    entry_state: config_entries.ConfigEntryState,
) -> None:
    """Test a token refresh reauth error starts reauthentication."""
    aioclient_mock.post(TOKEN_URL, status=HTTPStatus.BAD_REQUEST, json={})

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)
    config_entry.mock_state(hass, entry_state)

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    with (
        patch.object(config_entry, "async_start_reauth_if_available") as start_reauth,
        pytest.raises(OAuth2TokenRequestReauthError),
    ):
        await session.async_ensure_token_valid()

    start_reauth.assert_called_once_with(hass)


async def test_oauth_session_reauth_error_starts_reauth_when_caller_recovers(
    hass: HomeAssistant,
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauth starts even when the caller treats the error as recoverable.

    The token request errors subclass ClientResponseError, so a caller catching
    ClientError would otherwise retry a revoked refresh token indefinitely.
    """
    aioclient_mock.post(TOKEN_URL, status=HTTPStatus.BAD_REQUEST, json={})

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)
    config_entry.mock_state(hass, config_entries.ConfigEntryState.SETUP_IN_PROGRESS)

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    with (
        patch.object(config_entry, "async_start_reauth_if_available") as start_reauth,
        pytest.raises(ClientError),
    ):
        await session.async_ensure_token_valid()

    start_reauth.assert_called_once_with(hass)


@pytest.mark.parametrize(
    "status_code",
    [
        pytest.param(HTTPStatus.TOO_MANY_REQUESTS, id="transient"),
        pytest.param(600, id="generic"),
    ],
)
async def test_oauth_session_recoverable_error_does_not_start_reauth(
    hass: HomeAssistant,
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
    status_code: int,
) -> None:
    """Test a recoverable token refresh error does not start reauthentication."""
    aioclient_mock.post(TOKEN_URL, status=status_code, json={})

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)
    config_entry.mock_state(hass, config_entries.ConfigEntryState.LOADED)

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, local_impl)
    with (
        patch.object(config_entry, "async_start_reauth_if_available") as start_reauth,
        pytest.raises(OAuth2TokenRequestError),
    ):
        await session.async_ensure_token_valid()

    start_reauth.assert_not_called()


async def test_oauth2_without_secret_init(
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check authorize callback without secret initalizated."""
    client = await hass_client_no_auth()
    resp = await client.get("/auth/external/callback?code=abcd&state=qwer")
    assert resp.status == 400


@pytest.mark.usefixtures("current_request_with_host")
async def test_abort_oauth_with_pkce_rejected(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl_pkce: config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check bad oauth token."""
    flow_handler.async_register_implementation(hass, local_impl_pkce)

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    code_challenge = local_impl_pkce.compute_code_challenge(MOCK_SECRET_TOKEN_URLSAFE)
    assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP

    assert result["url"].startswith(f"{AUTHORIZE_URL}?")
    assert f"client_id={CLIENT_ID}" in result["url"]
    assert "redirect_uri=https://example.com/auth/external/callback" in result["url"]
    assert f"state={state}" in result["url"]
    assert "scope=read+write" in result["url"]
    assert "response_type=code" in result["url"]
    assert f"code_challenge={code_challenge}" in result["url"]
    assert "code_challenge_method=S256" in result["url"]

    client = await hass_client_no_auth()
    resp = await client.get(
        f"/auth/external/callback?error=access_denied&state={state}"
    )
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "user_rejected_authorize"
    assert result["description_placeholders"] == {"error": "access_denied"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_oauth_with_pkce_adds_code_verifier_to_token_resolve(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl_pkce: config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check pkce flow."""

    mock_integration(
        hass,
        MockModule(
            domain=TEST_DOMAIN,
            async_setup_entry=AsyncMock(return_value=True),
        ),
    )
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)
    flow_handler.async_register_implementation(hass, local_impl_pkce)

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    code_challenge = local_impl_pkce.compute_code_challenge(MOCK_SECRET_TOKEN_URLSAFE)
    assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP

    assert result["url"].startswith(f"{AUTHORIZE_URL}?")
    assert f"client_id={CLIENT_ID}" in result["url"]
    assert "redirect_uri=https://example.com/auth/external/callback" in result["url"]
    assert f"state={state}" in result["url"]
    assert "scope=read+write" in result["url"]
    assert "response_type=code" in result["url"]
    assert f"code_challenge={code_challenge}" in result["url"]
    assert "code_challenge_method=S256" in result["url"]

    # Setup the response when HA tries to fetch a token with the code
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": REFRESH_TOKEN,
            "access_token": ACCESS_TOKEN_1,
            "type": "bearer",
            "expires_in": 60,
        },
    )

    client = await hass_client_no_auth()
    # trigger the callback
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Verify the token resolve request occurred
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": "abcd",
        "redirect_uri": "https://example.com/auth/external/callback",
        "code_verifier": MOCK_SECRET_TOKEN_URLSAFE,
    }


@pytest.mark.parametrize("code_verifier_length", [40, 129])
def test_generate_code_verifier_invalid_length(code_verifier_length: int) -> None:
    """Test generate_code_verifier with an invalid length."""
    with pytest.raises(ValueError):
        config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce.generate_code_verifier(
            code_verifier_length
        )


@pytest.mark.parametrize("code_verifier", ["", "yyy", "a" * 129])
def test_compute_code_challenge_invalid_code_verifier(code_verifier: str) -> None:
    """Test compute_code_challenge with an invalid code_verifier."""
    with pytest.raises(ValueError):
        config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce.compute_code_challenge(
            code_verifier
        )


async def test_async_get_config_entry_impl_with_failing_and_succeeding_provider(
    hass: HomeAssistant,
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
) -> None:
    """Test async_get_config_entry_implementation with mixed providers."""

    async def failing_cloud_provider(
        _hass: HomeAssistant, _domain: str
    ) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
        """Provider that raises an exception."""
        raise config_entry_oauth2_flow.ImplementationUnavailableError

    async def successful_local_provider(
        _hass: HomeAssistant, _domain: str
    ) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
        """Provider that returns implementations."""
        return [local_impl]

    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, "cloud", failing_cloud_provider
    )
    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, "application_credentials", successful_local_provider
    )

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": local_impl.domain,
        },
    )

    # This should succeed and return the local implementation
    # even though the failing cloud provider raised an exception.
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )
    )
    assert implementation is local_impl


async def test_async_get_config_entry_implementation_with_failing_provider(
    hass: HomeAssistant,
) -> None:
    """Test async_get_config_entry_implementation with all failing providers."""

    async def failing_cloud_provider(
        _hass: HomeAssistant, _domain: str
    ) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
        """Provider that raises an exception."""
        raise config_entry_oauth2_flow.ImplementationUnavailableError

    async def empty_local_provider(
        _hass: HomeAssistant, _domain: str
    ) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
        """Provider that returns implementations."""
        return []

    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, "cloud", failing_cloud_provider
    )
    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, "application_credentials", empty_local_provider
    )

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
        },
    )

    # This should fail since the local provider returned an empty list
    # and the cloud provider raised an exception.
    with pytest.raises(config_entry_oauth2_flow.ImplementationUnavailableError):
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )


async def test_async_get_config_entry_implementation_missing_provider(
    hass: HomeAssistant,
) -> None:
    """Test async_get_config_entry_implementation when both providers are empty."""

    async def empty_provider(
        _hass: HomeAssistant, _domain: str
    ) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
        """Provider that returns implementations."""
        return []

    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, "cloud", empty_provider
    )
    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, "application_credentials", empty_provider
    )

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
        },
    )

    # This should fail since both providers are empty.
    with pytest.raises(ValueError, match="no longer available"):
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )


@pytest.mark.parametrize(
    "header_name",
    [
        pytest.param("Authorization", id="canonical_casing"),
        pytest.param("authorization", id="lowercase"),
    ],
)
async def test_oauth2_request_replaces_caller_authorization_header(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    header_name: str,
) -> None:
    """Test the token replaces a caller supplied Authorization header."""
    aioclient_mock.post("https://example.com", status=201)

    await config_entry_oauth2_flow.async_oauth2_request(
        hass,
        {"access_token": ACCESS_TOKEN_1},
        "post",
        "https://example.com",
        headers={header_name: "Bearer caller supplied"},
    )

    assert len(aioclient_mock.mock_calls) == 1
    headers = CIMultiDict(aioclient_mock.mock_calls[0][3])

    # The token must not be sent as a second Authorization header
    assert headers.getall("Authorization") == [f"Bearer {ACCESS_TOKEN_1}"]


@pytest.mark.parametrize(
    ("status_code", "expected_state", "expected_translation_key"),
    [
        pytest.param(
            HTTPStatus.BAD_REQUEST,
            config_entries.ConfigEntryState.SETUP_ERROR,
            "oauth2_helper_reauth_required",
            id="reauth",
        ),
        pytest.param(
            HTTPStatus.TOO_MANY_REQUESTS,
            config_entries.ConfigEntryState.SETUP_RETRY,
            "oauth2_helper_refresh_transient",
            id="transient",
        ),
        pytest.param(
            600,
            config_entries.ConfigEntryState.SETUP_RETRY,
            "oauth2_helper_refresh_failed",
            id="generic",
        ),
    ],
)
@pytest.mark.usefixtures("flow_handler")
async def test_token_error_handled_without_integration_mapping(
    hass: HomeAssistant,
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
    status_code: int,
    expected_state: config_entries.ConfigEntryState,
    expected_translation_key: str | None,
) -> None:
    """Test setup maps token refresh errors when the integration does not.

    Every subclass carries config entry semantics, so the reauth subclass fails
    setup while the others retry it.
    """
    aioclient_mock.post(TOKEN_URL, status=status_code, json={})

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)

    async def async_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Refresh the token without mapping the OAuth errors."""
        session = config_entry_oauth2_flow.OAuth2Session(hass, entry, local_impl)
        await session.async_ensure_token_valid()
        return True

    mock_integration(hass, MockModule(TEST_DOMAIN, async_setup_entry=async_setup_entry))

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is expected_state
    assert config_entry.error_reason_translation_key == expected_translation_key


@pytest.mark.usefixtures("flow_handler")
async def test_token_error_integration_can_handle_it_itself(
    hass: HomeAssistant,
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test an integration can still map a token error to its own behaviour."""
    aioclient_mock.post(TOKEN_URL, status=HTTPStatus.BAD_REQUEST, json={})

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": TEST_DOMAIN,
            "token": {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN_1,
                "expires_at": 0,
            },
        },
    )
    config_entry.add_to_hass(hass)

    async def async_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Treat a reauth error as recoverable instead."""
        session = config_entry_oauth2_flow.OAuth2Session(hass, entry, local_impl)
        try:
            await session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise ConfigEntryNotReady from err
        return True

    mock_integration(hass, MockModule(TEST_DOMAIN, async_setup_entry=async_setup_entry))

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_unknown_implementation_asks_for_reauth(hass: HomeAssistant) -> None:
    """Test an entry referencing a removed implementation asks for reauth."""
    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={"auth_implementation": "removed", "token": {}},
    )
    config_entry.add_to_hass(hass)

    with pytest.raises(ConfigEntryAuthFailed) as err:
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )

    # Still a ValueError so integrations catching that keep working
    assert isinstance(err.value, ValueError)


@pytest.mark.usefixtures("flow_handler")
async def test_implementation_unavailable_retries_setup(hass: HomeAssistant) -> None:
    """Test an unavailable implementation retries setup without integration mapping."""

    async def failing_provider(
        hass: HomeAssistant, domain: str
    ) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
        """Fail like the cloud provider does when it cannot reach the server."""
        raise config_entry_oauth2_flow.ImplementationUnavailableError("cloud is down")

    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, "cloud", failing_provider
    )

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={"auth_implementation": TEST_DOMAIN, "token": {}},
    )
    config_entry.add_to_hass(hass)

    async def async_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Resolve the implementation without mapping the error."""
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
        return True

    mock_integration(hass, MockModule(TEST_DOMAIN, async_setup_entry=async_setup_entry))

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert (
        config_entry.error_reason_translation_key == "oauth2_implementation_unavailable"
    )


async def test_config_entry_implementation_unavailable_provider(
    hass: HomeAssistant,
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
) -> None:
    """Test a temporarily unavailable provider is not mistaken for a removed one.

    The entry is linked through the cloud, which is down, while the integration
    still offers a local implementation the user has not configured.
    """

    async def failing_cloud_provider(
        _hass: HomeAssistant, _domain: str
    ) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
        """Fail like the cloud provider does when it cannot reach the server."""
        raise config_entry_oauth2_flow.ImplementationUnavailableError("cloud is down")

    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, "cloud", failing_cloud_provider
    )
    # The integration still offers a local implementation, so the cloud failure
    # would otherwise be swallowed
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, local_impl
    )

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={"auth_implementation": "cloud"},
    )

    # Retry rather than asking the user to re-link an account that is fine
    with pytest.raises(config_entry_oauth2_flow.ImplementationUnavailableError):
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )


@pytest.mark.usefixtures("current_request_with_host")
async def test_pick_implementation_falls_back_when_removed(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
    local_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a stale implementation id does not break the flow.

    Reauth and reconfigure steps pass the implementation stored on the entry, which
    is gone once its credentials were removed.
    """
    mock_integration(
        hass,
        MockModule(TEST_DOMAIN, async_setup_entry=AsyncMock(return_value=True)),
    )
    flow_handler.async_register_implementation(hass, local_impl)

    class ReauthFlowHandler(flow_handler):
        """Handler passing the stored implementation, like spotify and watts do."""

        async def async_step_reauth(
            self, entry_data: dict[str, Any]
        ) -> config_entries.ConfigFlowResult:
            """Perform reauth with the implementation stored on the entry."""
            return await self.async_step_pick_implementation(
                user_input={
                    "implementation": self._get_reauth_entry().data[
                        "auth_implementation"
                    ]
                }
            )

        async def async_oauth_create_entry(
            self, data: dict
        ) -> config_entries.ConfigFlowResult:
            """Update the existing entry instead of creating a new one."""
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "auth_implementation": "removed",
            "token": {"refresh_token": REFRESH_TOKEN, "expires_at": 0},
        },
    )
    config_entry.add_to_hass(hass)

    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: ReauthFlowHandler}):
        # The stale id falls through to the only implementation left
        result = await config_entry.start_reauth_flow(hass)
        assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP

        state = config_entry_oauth2_flow._encode_jwt(
            hass,
            {
                "flow_id": result["flow_id"],
                "redirect_uri": "https://example.com/auth/external/callback",
            },
        )
        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
        assert resp.status == 200

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

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # The entry points at an implementation that exists again
    assert config_entry.data["auth_implementation"] == TEST_DOMAIN
    assert config_entry.data["token"]["access_token"] == ACCESS_TOKEN_1


async def test_pick_implementation_removed_without_any_left(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
) -> None:
    """Test a stale implementation id aborts cleanly when nothing is available."""
    flow = flow_handler()
    flow.hass = hass
    result = await flow.async_step_pick_implementation(
        user_input={"implementation": "removed"}
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "missing_configuration"
