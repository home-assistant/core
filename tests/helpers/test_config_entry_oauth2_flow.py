"""Tests for the Somfy config flow."""

import asyncio
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
from freezegun.api import FrozenDateTimeFactory
from multidict import CIMultiDict, CIMultiDictProxy
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
    mock_platform,
)
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
    MockLongPollSideEffect,
)
from pytest_homeassistant.typing import ClientSessionGenerator
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
DEVICE_CODE = "mock-device-code"
USER_CODE = "WDJB-MJHT"
VERIFICATION_URI = "https://example.com/device"
DEVICE_EXPIRES_IN = 900
DEVICE_INTERVAL = 5
DEVICE_AUTHORIZATION_RESPONSE = {
    "device_code": DEVICE_CODE,
    "user_code": USER_CODE,
    "verification_uri": VERIFICATION_URI,
    "expires_in": DEVICE_EXPIRES_IN,
    "interval": DEVICE_INTERVAL,
}
TOKEN_RESPONSE = {
    "refresh_token": REFRESH_TOKEN,
    "access_token": ACCESS_TOKEN_1,
    "token_type": "bearer",
    "expires_in": 60,
}
JSON_ACCEPT_HEADER = {"Accept": "application/json"}
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


@pytest.fixture
def device_flow_handler(
    hass: HomeAssistant,
) -> Generator[type[config_entry_oauth2_flow.AbstractOAuth2DeviceFlowHandler]]:
    """Return a registered device config flow."""

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    class TestDeviceFlowHandler(
        config_entry_oauth2_flow.AbstractOAuth2DeviceFlowHandler
    ):
        """Test device flow handler."""

        DOMAIN = TEST_DOMAIN

        @property
        def logger(self) -> logging.Logger:
            """Return logger."""
            return logging.getLogger(__name__)

    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestDeviceFlowHandler}):
        yield TestDeviceFlowHandler


class ScopedDeviceFlowImplementation(config_entry_oauth2_flow.DeviceFlowImplementation):
    """Device flow implementation that asks for a scope."""

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data for the device authorization request."""
        return {"scope": "read write", "audience": None}


@pytest.fixture
def device_impl(
    hass: HomeAssistant,
) -> config_entry_oauth2_flow.DeviceFlowImplementation:
    """Device flow implementation."""
    return ScopedDeviceFlowImplementation(
        hass, TEST_DOMAIN, CLIENT_ID, AUTHORIZE_URL, TOKEN_URL
    )


@pytest.fixture
def mock_device_integration(hass: HomeAssistant) -> None:
    """Mock the integration the device flow creates entries for."""
    mock_integration(
        hass,
        MockModule(domain=TEST_DOMAIN, async_setup_entry=AsyncMock(return_value=True)),
    )


class FakeSleep:
    """Record the device flow poll waits and advance the frozen clock instead."""

    def __init__(self, freezer: FrozenDateTimeFactory) -> None:
        """Initialize the fake sleep."""
        self._freezer = freezer
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        """Advance the clock instead of waiting."""
        if not delay:
            await _real_sleep(0)
            return
        self.delays.append(delay)
        self._freezer.tick(delay)


_real_sleep = asyncio.sleep


@pytest.fixture
def poll_sleep(freezer: FrozenDateTimeFactory) -> Generator[FakeSleep]:
    """Patch the device flow poll wait."""
    fake_sleep = FakeSleep(freezer)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.asyncio.sleep", fake_sleep
    ):
        yield fake_sleep


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


def test_authorization_code_alias() -> None:
    """Test the old base class name stays the authorization code base class."""
    assert (
        config_entry_oauth2_flow.AbstractOAuth2Implementation
        is config_entry_oauth2_flow.AbstractAuthorizationCodeImplementation
    )
    assert not issubclass(
        config_entry_oauth2_flow.DeviceFlowImplementation,
        config_entry_oauth2_flow.AbstractAuthorizationCodeImplementation,
    )
    assert issubclass(
        config_entry_oauth2_flow.DeviceFlowImplementation,
        config_entry_oauth2_flow.AbstractOAuth2BaseImplementation,
    )


def _device_authorization(
    expires_in: int = DEVICE_EXPIRES_IN, interval: int = DEVICE_INTERVAL
) -> config_entry_oauth2_flow.DeviceAuthorization:
    """Return a device authorization as the server granted it."""
    return config_entry_oauth2_flow.DeviceAuthorization(
        device_code=DEVICE_CODE,
        user_code=USER_CODE,
        verification_uri=VERIFICATION_URI,
        verification_uri_complete=None,
        expires_in=expires_in,
        interval=interval,
    )


def _mock_token_responses(
    aioclient_mock: AiohttpClientMocker, responses: list[dict[str, Any]]
) -> None:
    """Answer the token endpoint with the given responses in order."""
    pending = list(responses)

    async def _next_response(
        method: str, url: URL, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(method=method, url=url, **pending.pop(0))

    aioclient_mock.post(TOKEN_URL, side_effect=_next_response)


async def _start_device_flow(hass: HomeAssistant) -> config_entries.ConfigFlowResult:
    """Start the device flow and pick the test implementation."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"implementation": TEST_DOMAIN}
    )


@pytest.mark.usefixtures("device_flow_handler", "mock_device_integration")
async def test_device_flow_full_flow(
    hass: HomeAssistant,
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    poll_sleep: FakeSleep,
) -> None:
    """Test the device flow from registration to the config entry."""
    aioclient_mock.post(AUTHORIZE_URL, json=DEVICE_AUTHORIZATION_RESPONSE)
    token_endpoint = MockLongPollSideEffect()
    aioclient_mock.post(TOKEN_URL, side_effect=token_endpoint)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, device_impl
    )

    result = await _start_device_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "device_flow"
    assert result["progress_action"] == "wait_for_device"
    assert result["description_placeholders"] == {
        "url": VERIFICATION_URI,
        "url_complete": VERIFICATION_URI,
        "code": USER_CODE,
    }

    # Showing the progress again neither registers again nor finishes the flow
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["description_placeholders"] == {
        "url": VERIFICATION_URI,
        "url_complete": VERIFICATION_URI,
        "code": USER_CODE,
    }

    token_endpoint.queue_response(status=400, json={"error": "authorization_pending"})
    token_endpoint.queue_response(json=TOKEN_RESPONSE)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Device authorization"
    assert result["data"] == {
        "auth_implementation": TEST_DOMAIN,
        "token": {**TOKEN_RESPONSE, "expires_at": time.time() + 60},
    }
    # The first poll waits the interval too (RFC 8628 section 3.5)
    assert poll_sleep.delays == [DEVICE_INTERVAL, DEVICE_INTERVAL]
    poll_request = {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "device_code": DEVICE_CODE,
        "client_id": CLIENT_ID,
    }
    assert [call[1:] for call in aioclient_mock.mock_calls] == [
        (
            URL(AUTHORIZE_URL),
            {"scope": "read write", "client_id": CLIENT_ID},
            JSON_ACCEPT_HEADER,
        ),
        (URL(TOKEN_URL), poll_request, JSON_ACCEPT_HEADER),
        (URL(TOKEN_URL), poll_request, JSON_ACCEPT_HEADER),
    ]


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"text": "not json"}, id="invalid_json"),
        pytest.param({"json": ["not", "a", "dict"]}, id="not_an_object"),
        *(
            pytest.param(
                {
                    "json": {
                        key: value
                        for key, value in DEVICE_AUTHORIZATION_RESPONSE.items()
                        if key != missing
                    }
                },
                id=f"missing_{missing}",
            )
            for missing in (
                "device_code",
                "user_code",
                "verification_uri",
                "expires_in",
            )
        ),
        pytest.param(
            {"json": {**DEVICE_AUTHORIZATION_RESPONSE, "expires_in": "soon"}},
            id="expires_in_not_a_number",
        ),
    ],
)
@pytest.mark.usefixtures("device_flow_handler")
async def test_device_flow_invalid_registration(
    hass: HomeAssistant,
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
) -> None:
    """Test an unusable device authorization response aborts before polling."""
    aioclient_mock.post(AUTHORIZE_URL, **response)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, device_impl
    )

    result = await _start_device_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "oauth_error"
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        pytest.param(
            {"json": DEVICE_AUTHORIZATION_RESPONSE},
            _device_authorization(),
            id="json",
        ),
        pytest.param(
            {
                "json": {
                    **DEVICE_AUTHORIZATION_RESPONSE,
                    "verification_uri_complete": f"{VERIFICATION_URI}?code=1",
                }
            },
            config_entry_oauth2_flow.DeviceAuthorization(
                device_code=DEVICE_CODE,
                user_code=USER_CODE,
                verification_uri=VERIFICATION_URI,
                verification_uri_complete=f"{VERIFICATION_URI}?code=1",
                expires_in=DEVICE_EXPIRES_IN,
                interval=DEVICE_INTERVAL,
            ),
            id="verification_uri_complete",
        ),
        pytest.param(
            {
                "json": {
                    "device_code": DEVICE_CODE,
                    "user_code": USER_CODE,
                    "verification_url": VERIFICATION_URI,
                    "expires_in": str(DEVICE_EXPIRES_IN),
                    "interval": "7",
                }
            },
            _device_authorization(interval=7),
            id="verification_url_and_string_numbers",
        ),
        pytest.param(
            {
                "json": {
                    key: value
                    for key, value in DEVICE_AUTHORIZATION_RESPONSE.items()
                    if key != "interval"
                }
            },
            _device_authorization(interval=5),
            id="default_interval",
        ),
        pytest.param(
            {"json": {**DEVICE_AUTHORIZATION_RESPONSE, "interval": 0}},
            _device_authorization(interval=5),
            id="interval_below_minimum",
        ),
    ],
)
async def test_device_flow_register_device(
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    expected: config_entry_oauth2_flow.DeviceAuthorization,
) -> None:
    """Test the device authorization response is parsed tolerantly."""
    aioclient_mock.post(AUTHORIZE_URL, **response)

    assert await device_impl.async_register_device() == expected


@pytest.mark.parametrize(
    ("response", "expected_abort_reason"),
    [
        pytest.param(
            {"status": HTTPStatus.TOO_MANY_REQUESTS}, "oauth_failed", id="429"
        ),
        pytest.param(
            {"status": HTTPStatus.INTERNAL_SERVER_ERROR}, "oauth_failed", id="500"
        ),
        pytest.param(
            {"status": HTTPStatus.UNAUTHORIZED}, "oauth_unauthorized", id="401"
        ),
        pytest.param(
            {"status": HTTPStatus.BAD_REQUEST, "json": {"error": "invalid_client"}},
            "oauth_unauthorized",
            id="400_invalid_client",
        ),
        pytest.param({"exc": ClientError()}, "oauth_failed", id="connection_error"),
        pytest.param(
            {"exc": TimeoutError()}, "authorize_url_timeout", id="timeout_error"
        ),
    ],
)
@pytest.mark.usefixtures("device_flow_handler")
async def test_device_flow_registration_errors(
    hass: HomeAssistant,
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    expected_abort_reason: str,
) -> None:
    """Test a failed device authorization request aborts the flow."""
    aioclient_mock.post(AUTHORIZE_URL, **response)
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, device_impl
    )

    result = await _start_device_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == expected_abort_reason


@pytest.mark.parametrize(
    ("response", "expected_abort_reason", "placeholders"),
    [
        pytest.param(
            {"status": 400, "json": {"error": "access_denied"}},
            "user_rejected_authorize",
            {"error": "access_denied"},
            id="access_denied",
        ),
        pytest.param(
            {"status": 400, "json": {"error": "expired_token"}},
            "oauth_timeout",
            None,
            id="expired_token",
        ),
        pytest.param(
            {"status": 400, "json": {"error": "invalid_grant"}},
            "oauth_error",
            None,
            id="unknown_error_code",
        ),
        pytest.param(
            {"json": {**TOKEN_RESPONSE, "expires_in": "soon"}},
            "oauth_error",
            None,
            id="invalid_expires_in",
        ),
        pytest.param(
            {"exc": RuntimeError("boom")},
            "oauth_error",
            None,
            id="unexpected_exception",
        ),
    ],
)
@pytest.mark.usefixtures("device_flow_handler", "mock_device_integration", "poll_sleep")
async def test_device_flow_poll_aborts(
    hass: HomeAssistant,
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    expected_abort_reason: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Test the flow aborts when polling for the token fails."""
    aioclient_mock.post(AUTHORIZE_URL, json=DEVICE_AUTHORIZATION_RESPONSE)
    _mock_token_responses(aioclient_mock, [response])
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, device_impl
    )

    result = await _start_device_flow(hass)
    # Polling already failed while the task started eagerly, the progress
    # is shown anyway
    assert result["type"] is data_entry_flow.FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == expected_abort_reason
    assert result["description_placeholders"] == placeholders


@pytest.mark.usefixtures("poll_sleep")
async def test_device_flow_handler_authorize_data(
    hass: HomeAssistant,
    device_flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2DeviceFlowHandler],
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the flow handler adds its authorize data, such as the scope."""
    aioclient_mock.post(AUTHORIZE_URL, json=DEVICE_AUTHORIZATION_RESPONSE)
    _mock_token_responses(
        aioclient_mock, [{"status": 400, "json": {"error": "access_denied"}}]
    )
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, device_impl
    )

    with patch.object(
        device_flow_handler, "extra_authorize_data", {"scope": "repo", "prompt": None}
    ):
        await _start_device_flow(hass)
    await hass.async_block_till_done()

    assert aioclient_mock.mock_calls[0][1:] == (
        URL(AUTHORIZE_URL),
        {"scope": "repo", "client_id": CLIENT_ID},
        JSON_ACCEPT_HEADER,
    )


@pytest.mark.usefixtures("device_flow_handler", "poll_sleep")
async def test_device_flow_url_complete_placeholder(
    hass: HomeAssistant,
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the progress links the complete verification uri when given."""
    aioclient_mock.post(
        AUTHORIZE_URL,
        json={
            **DEVICE_AUTHORIZATION_RESPONSE,
            "verification_uri_complete": f"{VERIFICATION_URI}?code={USER_CODE}",
        },
    )
    _mock_token_responses(
        aioclient_mock, [{"status": 400, "json": {"error": "access_denied"}}]
    )
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, device_impl
    )

    result = await _start_device_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["description_placeholders"] == {
        "url": VERIFICATION_URI,
        "url_complete": f"{VERIFICATION_URI}?code={USER_CODE}",
        "code": USER_CODE,
    }
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("responses", "expected_token"),
    [
        pytest.param(
            [{"status": 400, "json": {"error": "authorization_pending"}}] * 2
            + [{"json": TOKEN_RESPONSE}],
            TOKEN_RESPONSE,
            id="pending_then_success",
        ),
        pytest.param(
            [
                {"json": {"error": "authorization_pending"}},
                {"json": TOKEN_RESPONSE},
            ],
            TOKEN_RESPONSE,
            id="error_in_200_response",
        ),
        pytest.param(
            [{"json": {"access_token": ACCESS_TOKEN_1, "token_type": "bearer"}}],
            {
                "access_token": ACCESS_TOKEN_1,
                "token_type": "bearer",
                "expires_in": config_entry_oauth2_flow.DEVICE_FLOW_DEFAULT_EXPIRES_IN,
            },
            id="without_expires_in",
        ),
    ],
)
async def test_device_flow_check_activation(
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    poll_sleep: FakeSleep,
    responses: list[dict[str, Any]],
    expected_token: dict[str, Any],
) -> None:
    """Test polling returns the token once the user authorized the device."""
    _mock_token_responses(aioclient_mock, responses)

    token = await device_impl.async_check_device_activation(_device_authorization())

    assert token == expected_token
    assert poll_sleep.delays == [DEVICE_INTERVAL] * len(responses)
    assert aioclient_mock.call_count == len(responses)


@pytest.mark.parametrize(
    ("responses", "expected_exception"),
    [
        pytest.param(
            [{"status": 400, "json": {"error": "access_denied"}}],
            config_entry_oauth2_flow.DeviceFlowUnauthorized,
            id="access_denied",
        ),
        pytest.param(
            [{"json": {"error": "access_denied"}}],
            config_entry_oauth2_flow.DeviceFlowUnauthorized,
            id="access_denied_in_200_response",
        ),
        pytest.param(
            [{"status": 400, "json": {"error": "expired_token"}}],
            config_entry_oauth2_flow.DeviceFlowTimeout,
            id="expired_token",
        ),
        pytest.param(
            [{"status": 400, "json": {"error": "unsupported_grant_type"}}],
            config_entry_oauth2_flow.DeviceFlowError,
            id="unknown_error_code",
        ),
        pytest.param(
            [{"status": 400, "json": {"error": 5}}],
            config_entry_oauth2_flow.DeviceFlowError,
            id="error_code_not_a_string",
        ),
        pytest.param(
            [{"status": 400, "text": "Bad Request"}],
            config_entry_oauth2_flow.DeviceFlowError,
            id="400_without_error_code",
        ),
        pytest.param(
            [{"text": "<html>not json</html>"}],
            config_entry_oauth2_flow.DeviceFlowError,
            id="invalid_json",
        ),
        pytest.param(
            [{"json": {"token_type": "bearer"}}],
            config_entry_oauth2_flow.DeviceFlowError,
            id="success_without_access_token",
        ),
    ],
)
async def test_device_flow_check_activation_errors(
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    poll_sleep: FakeSleep,
    responses: list[dict[str, Any]],
    expected_exception: type[config_entry_oauth2_flow.DeviceFlowError],
) -> None:
    """Test polling stops on a final error."""
    _mock_token_responses(aioclient_mock, responses)

    with pytest.raises(expected_exception):
        await device_impl.async_check_device_activation(_device_authorization())

    assert aioclient_mock.call_count == len(responses)


@pytest.mark.parametrize(
    ("slow_down", "expected_delays"),
    [
        pytest.param({"error": "slow_down"}, [5, 10], id="increment"),
        pytest.param(
            {"error": "slow_down", "interval": "20"}, [5, 20], id="server_interval"
        ),
        pytest.param(
            {"error": "slow_down", "interval": 600}, [5, 120], id="capped_interval"
        ),
        pytest.param(
            {"error": "slow_down", "interval": "soon"},
            [5, 10],
            id="invalid_server_interval",
        ),
    ],
)
async def test_device_flow_slow_down(
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    poll_sleep: FakeSleep,
    slow_down: dict[str, Any],
    expected_delays: list[int],
) -> None:
    """Test slow_down raises the interval for the next polls."""
    _mock_token_responses(
        aioclient_mock,
        [{"status": 400, "json": slow_down}, {"json": TOKEN_RESPONSE}],
    )

    token = await device_impl.async_check_device_activation(_device_authorization())

    assert token == TOKEN_RESPONSE
    assert poll_sleep.delays == expected_delays


@pytest.mark.parametrize(
    ("interval", "failure", "expected_delays"),
    [
        pytest.param(2, {"exc": ClientError()}, [2, 4], id="connection_error"),
        pytest.param(2, {"exc": TimeoutError()}, [2, 4], id="timeout"),
        pytest.param(40, {"exc": TimeoutError()}, [40, 60], id="capped"),
        pytest.param(90, {"exc": TimeoutError()}, [90, 90], id="above_cap"),
        pytest.param(
            2,
            {"status": HTTPStatus.TOO_MANY_REQUESTS},
            [2, 4],
            id="too_many_requests",
        ),
        pytest.param(
            2,
            {"status": HTTPStatus.INTERNAL_SERVER_ERROR, "json": {"error": "x"}},
            [2, 4],
            id="server_error",
        ),
    ],
)
async def test_device_flow_connection_failure_backs_off(
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    poll_sleep: FakeSleep,
    interval: int,
    failure: dict[str, Any],
    expected_delays: list[int],
) -> None:
    """Test a poll without a usable response retries with a longer interval."""
    _mock_token_responses(aioclient_mock, [failure, {"json": TOKEN_RESPONSE}])

    token = await device_impl.async_check_device_activation(
        _device_authorization(interval=interval)
    )

    assert token == TOKEN_RESPONSE
    assert poll_sleep.delays == expected_delays


async def test_device_flow_deadline(
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    poll_sleep: FakeSleep,
) -> None:
    """Test polling stops when the device code expired."""
    _mock_token_responses(
        aioclient_mock,
        [{"status": 400, "json": {"error": "authorization_pending"}}] * 2,
    )

    with pytest.raises(config_entry_oauth2_flow.DeviceFlowTimeout):
        await device_impl.async_check_device_activation(
            _device_authorization(expires_in=10, interval=4)
        )

    assert poll_sleep.delays == [4, 4, 4]
    assert aioclient_mock.call_count == 2


@pytest.mark.usefixtures("device_flow_handler", "mock_device_integration", "poll_sleep")
async def test_device_flow_token_without_expiry(
    hass: HomeAssistant,
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a token without expires_in is stored as long lived and refreshes."""
    aioclient_mock.post(AUTHORIZE_URL, json=DEVICE_AUTHORIZATION_RESPONSE)
    _mock_token_responses(
        aioclient_mock,
        [
            {
                "json": {
                    "access_token": ACCESS_TOKEN_1,
                    "refresh_token": REFRESH_TOKEN,
                    "token_type": "bearer",
                }
            },
            {"json": {"access_token": ACCESS_TOKEN_2, "token_type": "bearer"}},
        ],
    )
    config_entry_oauth2_flow.async_register_implementation(
        hass, TEST_DOMAIN, device_impl
    )

    result = await _start_device_flow(hass)
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    default_expires_in = config_entry_oauth2_flow.DEVICE_FLOW_DEFAULT_EXPIRES_IN
    assert result["data"]["token"] == {
        "access_token": ACCESS_TOKEN_1,
        "refresh_token": REFRESH_TOKEN,
        "token_type": "bearer",
        "expires_in": default_expires_in,
        "expires_at": time.time() + default_expires_in,
    }
    entry = result["result"]
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, device_impl)
    assert session.valid_token

    freezer.tick(default_expires_in)
    assert not session.valid_token
    await session.async_ensure_token_valid()

    assert entry.data["token"] == {
        "access_token": ACCESS_TOKEN_2,
        "refresh_token": REFRESH_TOKEN,
        "token_type": "bearer",
        "expires_in": default_expires_in,
        "expires_at": time.time() + default_expires_in,
    }
    assert aioclient_mock.mock_calls[-1][1:] == (
        URL(TOKEN_URL),
        {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": REFRESH_TOKEN,
        },
        JSON_ACCEPT_HEADER,
    )


async def test_device_flow_refresh_without_refresh_token(
    device_impl: config_entry_oauth2_flow.DeviceFlowImplementation,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a token without refresh_token needs reauth instead of a refresh."""
    with pytest.raises(ConfigEntryAuthFailed) as exc_info:
        await device_impl.async_refresh_token(
            {"access_token": ACCESS_TOKEN_1, "token_type": "bearer"}
        )

    assert exc_info.value.translation_key == "oauth2_helper_reauth_required"
    assert aioclient_mock.call_count == 0


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


async def test_local_refresh_token_client_secret_basic(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test overriding token_auth_method sends the credentials as basic auth."""

    class BasicAuthImplementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
        token_auth_method = "client_secret_basic"

    local_impl = BasicAuthImplementation(
        hass, TEST_DOMAIN, CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL
    )
    aioclient_mock.post(
        TOKEN_URL, json={"access_token": ACCESS_TOKEN_2, "expires_in": 100}
    )

    await local_impl.async_refresh_token(
        {"refresh_token": REFRESH_TOKEN, "access_token": ACCESS_TOKEN_1}
    )

    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "client_id": CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
    }
    # base64 of "1234:5678"
    assert aioclient_mock.mock_calls[0][3] == {"Authorization": "Basic MTIzNDo1Njc4"}


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
            async_setup_entry=AsyncMock(return_value=None),
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
    ) -> None:
        """Refresh the token without mapping the OAuth errors."""
        session = config_entry_oauth2_flow.OAuth2Session(hass, entry, local_impl)
        await session.async_ensure_token_valid()

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
    ) -> None:
        """Treat a reauth error as recoverable instead."""
        session = config_entry_oauth2_flow.OAuth2Session(hass, entry, local_impl)
        try:
            await session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise ConfigEntryNotReady from err

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
    ) -> None:
        """Resolve the implementation without mapping the error."""
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )

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
        MockModule(TEST_DOMAIN, async_setup_entry=AsyncMock(return_value=None)),
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
