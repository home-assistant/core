"""Tests for the Bbox API client."""

from http import HTTPStatus
from typing import Any
from unittest.mock import patch

from aiohttp import ClientConnectionError
import pytest
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

from homeassistant.components.bbox.api import (
    BboxApi,
    BboxAuthError,
    BboxConnectionError,
    BboxError,
    BboxRateLimitError,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DEVICE_INFO_RESPONSE,
    DEVICE_URL,
    HOSTS_RESPONSE,
    HOSTS_URL,
    LOGIN_URL,
    MAIN_NETWORK_HOSTS,
    PASSWORD,
    UNAUTHORIZED_BODY,
    WAN_IP_STATS_RESPONSE,
    WAN_IP_STATS_URL,
)


class HostsAfterLoginSideEffect:
    """Answer the hosts endpoint 401 once, then with the hosts list."""

    def __init__(self) -> None:
        """Initialize the call counter."""
        self.calls = 0

    async def __call__(
        self, method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        """Return the answer for the current call."""
        self.calls += 1
        if self.calls == 1:
            return AiohttpClientMockResponse(
                method=method,
                url=URL(url),
                status=HTTPStatus.UNAUTHORIZED,
                json=UNAUTHORIZED_BODY,
            )
        return AiohttpClientMockResponse(
            method=method, url=URL(url), json=HOSTS_RESPONSE
        )


async def test_get_ip_stats(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the WAN stats are extracted from the single-element array."""
    aioclient_mock.get(WAN_IP_STATS_URL, json=WAN_IP_STATS_RESPONSE)
    api = BboxApi(async_get_clientsession(hass), None)
    stats = await api.get_ip_stats()
    assert stats == WAN_IP_STATS_RESPONSE[0]["wan"]["ip"]["stats"]


async def test_get_bbox_info(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the device info is extracted from the single-element array."""
    aioclient_mock.get(DEVICE_URL, json=DEVICE_INFO_RESPONSE)
    api = BboxApi(async_get_clientsession(hass), None)
    assert await api.get_bbox_info() == DEVICE_INFO_RESPONSE[0]


async def test_get_ip_stats_and_info(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the grouped call fetches both endpoints."""
    aioclient_mock.get(WAN_IP_STATS_URL, json=WAN_IP_STATS_RESPONSE)
    aioclient_mock.get(DEVICE_URL, json=DEVICE_INFO_RESPONSE)
    api = BboxApi(async_get_clientsession(hass), None)
    stats, info = await api.get_ip_stats_and_info()
    assert stats == WAN_IP_STATS_RESPONSE[0]["wan"]["ip"]["stats"]
    assert info == DEVICE_INFO_RESPONSE[0]
    assert aioclient_mock.call_count == 2


async def test_grouped_fetch_logs_in_once(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that concurrent 401s on both endpoints share a single login."""
    state = {"logged_in": False}
    payloads = {
        str(WAN_IP_STATS_URL): WAN_IP_STATS_RESPONSE,
        str(DEVICE_URL): DEVICE_INFO_RESPONSE,
    }

    async def get_side_effect(
        method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        if not state["logged_in"]:
            return AiohttpClientMockResponse(
                method=method,
                url=URL(url),
                status=HTTPStatus.UNAUTHORIZED,
                json=UNAUTHORIZED_BODY,
            )
        return AiohttpClientMockResponse(
            method=method, url=URL(url), json=payloads[str(url)]
        )

    async def post_side_effect(
        method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        state["logged_in"] = True
        return AiohttpClientMockResponse(
            method=method, url=URL(url), status=HTTPStatus.OK
        )

    aioclient_mock.get(WAN_IP_STATS_URL, side_effect=get_side_effect)
    aioclient_mock.get(DEVICE_URL, side_effect=get_side_effect)
    aioclient_mock.post(LOGIN_URL, side_effect=post_side_effect)
    api = BboxApi(async_get_clientsession(hass), PASSWORD)
    stats, info = await api.get_ip_stats_and_info()
    assert stats == WAN_IP_STATS_RESPONSE[0]["wan"]["ip"]["stats"]
    assert info == DEVICE_INFO_RESPONSE[0]
    logins = [call for call in aioclient_mock.mock_calls if call[0].upper() == "POST"]
    assert len(logins) == 1


async def test_grouped_fetch_failed_login_attempted_once(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a failed login is shared: one POST /login for concurrent 401s."""
    aioclient_mock.get(
        WAN_IP_STATS_URL, status=HTTPStatus.UNAUTHORIZED, json=UNAUTHORIZED_BODY
    )
    aioclient_mock.get(
        DEVICE_URL, status=HTTPStatus.UNAUTHORIZED, json=UNAUTHORIZED_BODY
    )
    aioclient_mock.post(LOGIN_URL, status=HTTPStatus.UNAUTHORIZED)
    api = BboxApi(async_get_clientsession(hass), PASSWORD)
    with pytest.raises(BboxAuthError):
        await api.get_ip_stats_and_info()
    logins = [call for call in aioclient_mock.mock_calls if call[0].upper() == "POST"]
    assert len(logins) == 1


async def test_stale_auth_error_is_retried_without_login(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a 401 predating a concurrent login does not trigger a new login."""
    aioclient_mock.get(DEVICE_URL, json=DEVICE_INFO_RESPONSE)
    aioclient_mock.post(LOGIN_URL)
    api = BboxApi(async_get_clientsession(hass), PASSWORD)
    stale_error = BboxAuthError(
        "Authentication required by the Bbox", start_epoch=0, stale=True
    )
    with patch.object(
        api, "_request", side_effect=[stale_error, DEVICE_INFO_RESPONSE[0]]
    ):
        info = await api._request_with_login_retry("device")
    assert info == DEVICE_INFO_RESPONSE[0]
    logins = [call for call in aioclient_mock.mock_calls if call[0].upper() == "POST"]
    assert not logins


async def test_get_connected_devices(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the devices of the main network are returned."""
    aioclient_mock.get(HOSTS_URL, json=HOSTS_RESPONSE)
    api = BboxApi(async_get_clientsession(hass), PASSWORD)
    assert await api.get_connected_devices() == MAIN_NETWORK_HOSTS


async def test_get_connected_devices_without_password(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a 401 without a password raises an auth error."""
    aioclient_mock.get(
        HOSTS_URL, status=HTTPStatus.UNAUTHORIZED, json=UNAUTHORIZED_BODY
    )
    api = BboxApi(async_get_clientsession(hass), None)
    with pytest.raises(BboxAuthError, match="Authentication required"):
        await api.get_connected_devices()


async def test_get_connected_devices_logs_in_and_retries(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a 401 with a password logs in and retries once."""
    side_effect = HostsAfterLoginSideEffect()
    aioclient_mock.get(HOSTS_URL, side_effect=side_effect)
    aioclient_mock.post(LOGIN_URL)
    api = BboxApi(async_get_clientsession(hass), PASSWORD)
    assert await api.get_connected_devices() == MAIN_NETWORK_HOSTS
    assert side_effect.calls == 2
    logins = [call for call in aioclient_mock.mock_calls if call[0].upper() == "POST"]
    assert len(logins) == 1
    assert str(logins[0][1]) == LOGIN_URL
    assert logins[0][2] == {"password": PASSWORD, "remember": "1"}


@pytest.mark.parametrize(
    ("status", "exception", "match"),
    [
        (HTTPStatus.UNAUTHORIZED, BboxAuthError, "Invalid Bbox password"),
        (
            HTTPStatus.TOO_MANY_REQUESTS,
            BboxRateLimitError,
            "Too many Bbox login attempts",
        ),
    ],
)
async def test_login_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
    exception: type[BboxError],
    match: str,
) -> None:
    """Test that login failures raise typed errors."""
    aioclient_mock.get(
        HOSTS_URL, status=HTTPStatus.UNAUTHORIZED, json=UNAUTHORIZED_BODY
    )
    aioclient_mock.post(LOGIN_URL, status=status)
    api = BboxApi(async_get_clientsession(hass), PASSWORD)
    with pytest.raises(exception, match=match):
        await api.get_connected_devices()


async def test_login_without_password(hass: HomeAssistant) -> None:
    """Test that logging in without a password raises an auth error."""
    api = BboxApi(async_get_clientsession(hass), None)
    with pytest.raises(BboxAuthError, match="A password is required"):
        await api.login()


@pytest.mark.parametrize(
    "error", [ClientConnectionError("cannot connect to host"), TimeoutError()]
)
async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, error: Exception
) -> None:
    """Test that connection failures raise a typed connection error."""
    aioclient_mock.get(DEVICE_URL, exc=error)
    api = BboxApi(async_get_clientsession(hass), PASSWORD)
    with pytest.raises(BboxConnectionError, match="Cannot reach Bbox"):
        await api.get_bbox_info()


@pytest.mark.parametrize(
    ("status", "exception", "match"),
    [
        (HTTPStatus.BAD_REQUEST, BboxError, "Bbox error for"),
        (
            HTTPStatus.FORBIDDEN,
            BboxAuthError,
            "Authentication required",
        ),
        (
            HTTPStatus.TOO_MANY_REQUESTS,
            BboxRateLimitError,
            "Too many Bbox requests",
        ),
    ],
)
async def test_http_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
    exception: type[BboxError],
    match: str,
) -> None:
    """Test that an HTTP error status raises a typed error."""
    aioclient_mock.get(DEVICE_URL, status=status)
    # A 403 triggers the single login retry of the authenticated client.
    aioclient_mock.post(LOGIN_URL)
    api = BboxApi(async_get_clientsession(hass), PASSWORD)
    with pytest.raises(exception, match=match):
        await api.get_bbox_info()


@pytest.mark.parametrize(
    ("response", "method_name"),
    [
        ({"unrelated": "payload"}, "get_ip_stats"),
        ([], "get_ip_stats"),
        ({"unrelated": "payload"}, "get_connected_devices"),
        ([], "get_connected_devices"),
        ("just a string", "get_bbox_info"),
    ],
)
async def test_unexpected_payload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: object,
    method_name: str,
) -> None:
    """Test that an unexpected payload shape raises a typed error."""
    endpoints = {"get_ip_stats": WAN_IP_STATS_URL, "get_connected_devices": HOSTS_URL}
    aioclient_mock.get(endpoints[method_name], json=response)
    api = BboxApi(async_get_clientsession(hass), PASSWORD)
    with pytest.raises(BboxError, match="Unexpected Bbox payload"):
        await getattr(api, method_name)()
