"""Test the yolink authentication managers."""

import asyncio
import time
from typing import Any

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from yarl import URL
from yolink.const import OAUTH2_TOKEN
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.components.yolink.api import (
    ConfigEntryAuth,
    StaticTokenAuth,
    UACAuth,
)
from homeassistant.components.yolink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import TEST_SECRET_KEY, TEST_UAID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


def _uac_auth(hass: HomeAssistant) -> UACAuth:
    """Return a UAC authentication manager."""
    return UACAuth(async_get_clientsession(hass), TEST_UAID, TEST_SECRET_KEY)


async def _oauth_auth(hass: HomeAssistant, token: dict[str, Any]) -> ConfigEntryAuth:
    """Return an OAuth2 authentication manager for an entry holding token."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": DOMAIN, "token": token},
    )
    config_entry.add_to_hass(hass)
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )
    )
    return ConfigEntryAuth(
        hass,
        async_get_clientsession(hass),
        config_entry_oauth2_flow.OAuth2Session(hass, config_entry, implementation),
    )


async def test_uac_token_refreshed_after_half_its_lifetime(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the token is reused until half its lifetime has passed."""
    aioclient_mock.post(
        OAUTH2_TOKEN, json={"access_token": "token-1", "expires_in": 7200}
    )
    auth = _uac_auth(hass)

    assert auth.access_token() is None

    assert await auth.check_and_refresh_token() == "token-1"
    assert auth.access_token() == "token-1"
    assert aioclient_mock.call_count == 1

    freezer.tick(3599)
    assert await auth.check_and_refresh_token() == "token-1"
    assert aioclient_mock.call_count == 1

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN, json={"access_token": "token-2", "expires_in": 7200}
    )

    freezer.tick(2)
    assert await auth.check_and_refresh_token() == "token-2"
    assert auth.access_token() == "token-2"
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    ("status", "expected_error"),
    [
        pytest.param(401, YoLinkAuthFailError, id="unauthorized"),
        pytest.param(403, YoLinkAuthFailError, id="forbidden"),
        pytest.param(500, YoLinkClientError, id="server_error"),
    ],
)
async def test_uac_token_request_http_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    expected_error: type[YoLinkClientError],
) -> None:
    """Test an HTTP error from the token endpoint."""
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
        json={"error": "invalid_client", "error_description": "Bad credentials"},
    )
    auth = _uac_auth(hass)

    with pytest.raises(expected_error) as err:
        await auth.check_and_refresh_token()

    assert type(err.value) is expected_error
    assert err.value.code == "invalid_client"
    assert err.value.message == "Bad credentials"


async def test_uac_token_request_http_error_without_json_body(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an HTTP error carrying an unparsable body."""
    aioclient_mock.post(OAUTH2_TOKEN, status=502, text="<html>Bad gateway</html>")
    auth = _uac_auth(hass)

    with pytest.raises(YoLinkClientError) as err:
        await auth.check_and_refresh_token()

    assert err.value.code == "unknown"
    assert err.value.message == "HTTP 502"


@pytest.mark.parametrize(
    ("response", "code", "message"),
    [
        pytest.param(
            {"code": "000103", "desc": "Client is not exist"},
            "000103",
            "Client is not exist",
            id="yolink_error_body",
        ),
        pytest.param(
            {"error": "invalid_client", "error_description": "Bad secret key"},
            "invalid_client",
            "Bad secret key",
            id="oauth_error_body",
        ),
        pytest.param(
            {"desc": "Client is not exist"},
            "unknown",
            "Client is not exist",
            id="described_error_body",
        ),
        pytest.param(
            {"access_token": "", "code": "000103", "desc": "Client is not exist"},
            "000103",
            "Client is not exist",
            id="empty_access_token_with_error",
        ),
    ],
)
async def test_uac_token_request_error_body(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    code: str,
    message: str,
) -> None:
    """Test the token endpoint reporting an error with HTTP 200."""
    aioclient_mock.post(OAUTH2_TOKEN, json=response)
    auth = _uac_auth(hass)

    with pytest.raises(YoLinkAuthFailError) as err:
        await auth.check_and_refresh_token()

    assert err.value.code == code
    assert err.value.message == message


@pytest.mark.parametrize(
    "response_kwargs",
    [
        pytest.param({"text": "<html>Not JSON</html>"}, id="undecodable_body"),
        pytest.param({"json": ["token"]}, id="body_is_not_an_object"),
        # A body that reports no error is malformed rather than a refusal, so it
        # must not be reported as one and start a reauthentication.
        pytest.param({"json": {}}, id="empty_body"),
        pytest.param(
            {"json": {"access_token": "", "expires_in": 7200}},
            id="empty_access_token",
        ),
        pytest.param(
            {"json": {"access_token": 12345, "expires_in": 7200}},
            id="non_string_access_token",
        ),
        pytest.param({"json": {"access_token": "token-1"}}, id="missing_expires_in"),
        pytest.param(
            {"json": {"access_token": "token-1", "expires_in": "7200"}},
            id="non_numeric_expires_in",
        ),
        pytest.param(
            {"json": {"access_token": "token-1", "expires_in": True}},
            id="boolean_expires_in",
        ),
        pytest.param(
            {"json": {"access_token": "token-1", "expires_in": 0}},
            id="zero_expires_in",
        ),
        pytest.param(
            {"json": {"access_token": "token-1", "expires_in": -60}},
            id="negative_expires_in",
        ),
    ],
)
async def test_uac_token_request_unusable_success_body(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response_kwargs: dict[str, Any],
) -> None:
    """Test an HTTP 200 body that cannot be used as a token."""
    aioclient_mock.post(OAUTH2_TOKEN, **response_kwargs)
    auth = _uac_auth(hass)

    with pytest.raises(YoLinkClientError) as err:
        await auth.check_and_refresh_token()

    assert type(err.value) is YoLinkClientError
    assert err.value.code == "invalid_response"
    assert auth.access_token() is None


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ClientError("Connection reset"), id="client_error"),
        pytest.param(OSError("Network unreachable"), id="os_error"),
    ],
)
async def test_uac_token_request_network_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    exception: Exception,
) -> None:
    """Test a failing connection to the token endpoint."""
    aioclient_mock.post(OAUTH2_TOKEN, exc=exception)
    auth = _uac_auth(hass)

    with pytest.raises(YoLinkClientError) as err:
        await auth.check_and_refresh_token()

    assert type(err.value) is YoLinkClientError
    assert err.value.code == "request_failed"


async def test_uac_token_request_is_single_flight(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test concurrent callers share a single token request."""
    release = asyncio.Event()

    async def _blocked_token(
        method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        await release.wait()
        return AiohttpClientMockResponse(
            method, url, json={"access_token": "token-1", "expires_in": 7200}
        )

    aioclient_mock.post(OAUTH2_TOKEN, side_effect=_blocked_token)
    auth = _uac_auth(hass)

    tasks = [asyncio.create_task(auth.check_and_refresh_token()) for _ in range(5)]
    for _ in range(3):
        await asyncio.sleep(0)

    # Only the first caller reaches the token endpoint, the rest wait for it.
    assert aioclient_mock.call_count == 1
    release.set()

    assert await asyncio.gather(*tasks) == ["token-1"] * 5
    assert aioclient_mock.call_count == 1


async def test_uac_failed_refresh_keeps_cached_token(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing refresh leaves the cached token usable."""
    aioclient_mock.post(
        OAUTH2_TOKEN, json={"access_token": "token-1", "expires_in": 7200}
    )
    auth = _uac_auth(hass)

    assert await auth.check_and_refresh_token() == "token-1"

    aioclient_mock.clear_requests()
    aioclient_mock.post(OAUTH2_TOKEN, status=500, text="<html>Bad gateway</html>")

    freezer.tick(3601)
    with pytest.raises(YoLinkClientError):
        await auth.check_and_refresh_token()

    assert auth.access_token() == "token-1"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN, json={"access_token": "token-2", "expires_in": 7200}
    )

    assert await auth.check_and_refresh_token() == "token-2"


async def test_static_token_auth(hass: HomeAssistant) -> None:
    """Test the authentication manager for an already resolved token."""
    auth = StaticTokenAuth(async_get_clientsession(hass), "mock-access-token")

    assert auth.access_token() == "mock-access-token"
    assert await auth.check_and_refresh_token() == "mock-access-token"
    assert auth.http_auth_header() == "Bearer mock-access-token"


@pytest.mark.usefixtures("setup_credentials")
async def test_oauth_valid_token_is_kept(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a valid OAuth2 token is returned without refreshing."""
    auth = await _oauth_auth(
        hass,
        {
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_at": time.time() + 3600,
        },
    )

    assert auth.access_token() == "mock-access-token"
    assert await auth.check_and_refresh_token() == "mock-access-token"
    assert aioclient_mock.call_count == 0


@pytest.mark.usefixtures("setup_credentials")
async def test_oauth_expired_token_is_refreshed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an expired OAuth2 token is refreshed."""
    auth = await _oauth_auth(
        hass,
        {
            "access_token": "outdated-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_at": time.time() - 3600,
        },
    )

    assert auth.access_token() == "outdated-access-token"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
        },
    )

    assert await auth.check_and_refresh_token() == "new-access-token"
    assert auth.access_token() == "new-access-token"
    assert aioclient_mock.call_count == 1
