"""Test the EvolvIOT API client."""

from typing import Any, Self, cast
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError, ClientResponseError, ClientSession
import pytest

from homeassistant.components.evolviot.api import (
    EvolvIOTApi,
    EvolvIOTAuthError,
    EvolvIOTConnectionError,
    EvolvIOTDeviceAuthorizationDenied,
    EvolvIOTDeviceAuthorizationExpired,
    EvolvIOTDeviceAuthorizationPending,
    _local_status_headers,
    _sanitize_device_id_for_mdns,
    normalize_api_base_url,
)


class MockResponse:
    """Mock aiohttp response."""

    def __init__(
        self,
        *,
        status: int = 200,
        payload: Any | None = None,
        text: str = "",
    ) -> None:
        """Initialize the response."""
        self.status = status
        self.payload = payload if payload is not None else {}
        self._text = text

    async def __aenter__(self) -> Self:
        """Enter context manager."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Exit context manager."""

    def raise_for_status(self) -> None:
        """Raise for HTTP errors."""
        if self.status >= 400:
            raise ClientResponseError(Mock(), (), status=self.status)

    async def json(self, *, content_type: str | None = None) -> Any:
        """Return JSON payload."""
        return self.payload

    async def text(self) -> str:
        """Return text payload."""
        return self._text


class MockSession:
    """Mock aiohttp session."""

    def __init__(self, *responses: MockResponse) -> None:
        """Initialize the session."""
        self.responses = list(responses)
        self.get_calls: list[tuple[str, dict[str, Any]]] = []
        self.post_calls: list[tuple[str, dict[str, Any]]] = []
        self.request_calls: list[tuple[str, str, dict[str, Any]]] = []

    def _response(self) -> MockResponse:
        """Return the next response."""
        return self.responses.pop(0)

    def get(self, url: str, **kwargs: Any) -> MockResponse:
        """Mock GET."""
        self.get_calls.append((url, kwargs))
        return self._response()

    def post(self, url: str, **kwargs: Any) -> MockResponse:
        """Mock POST."""
        self.post_calls.append((url, kwargs))
        return self._response()

    def request(self, method: str, url: str, **kwargs: Any) -> MockResponse:
        """Mock request."""
        self.request_calls.append((method, url, kwargs))
        return self._response()


class ErrorSession(MockSession):
    """Mock session raising client errors."""

    def get(self, url: str, **kwargs: Any) -> MockResponse:
        """Mock GET failure."""
        raise ClientError

    def post(self, url: str, **kwargs: Any) -> MockResponse:
        """Mock POST failure."""
        raise ClientError

    def request(self, method: str, url: str, **kwargs: Any) -> MockResponse:
        """Mock request failure."""
        raise ClientError


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "https://api.evolviot.com/api/homeassistant"),
        ("https://example.com", "https://example.com/api/homeassistant"),
        ("https://example.com/api", "https://example.com/api/homeassistant"),
        (
            "https://example.com/api/homeassistant",
            "https://example.com/api/homeassistant",
        ),
    ],
)
def test_normalize_api_base_url(value: str | None, expected: str) -> None:
    """Test API base URL normalization."""
    assert normalize_api_base_url(value) == expected


def test_local_helpers() -> None:
    """Test local helper values."""
    assert _sanitize_device_id_for_mdns("Device_01!") == "device-01-"

    with (
        patch("homeassistant.components.evolviot.api.time.time", return_value=1000),
        patch(
            "homeassistant.components.evolviot.api.os.urandom",
            return_value=b"1" * 12,
        ),
    ):
        headers = _local_status_headers("uid", "device", "secret")

    assert headers["X-Evolv-Timestamp"] == "1000"
    assert headers["X-Evolv-Nonce"]
    assert headers["X-Evolv-Signature"]


async def test_health_and_validate() -> None:
    """Test health and validation requests."""
    session = MockSession(
        MockResponse(text="ok"),
        MockResponse(payload={"entities": []}),
    )
    api = EvolvIOTApi(cast(ClientSession, session), "https://example.com", "token")

    assert await api.async_validate() == {"entities": []}
    assert session.get_calls[0] == ("https://api.evolviot.com/health", {"ssl": True})
    assert session.request_calls[0][0:2] == (
        "GET",
        "https://example.com/api/homeassistant/devices",
    )


async def test_health_connection_error() -> None:
    """Test health connection errors."""
    api = EvolvIOTApi(cast(ClientSession, ErrorSession()), "https://example.com")

    with pytest.raises(EvolvIOTConnectionError):
        await api.async_health()


async def test_authorization_code_exchange() -> None:
    """Test OAuth authorization code exchange."""
    session = MockSession(MockResponse(payload={"access_token": "token"}))
    api = EvolvIOTApi(cast(ClientSession, session), "https://example.com")

    assert await api.async_exchange_authorization_code("code", "id", "secret") == {
        "access_token": "token"
    }
    assert session.post_calls[0][1]["data"] == {
        "grant_type": "authorization_code",
        "code": "code",
        "client_id": "id",
        "client_secret": "secret",
    }


@pytest.mark.parametrize(
    ("response", "exception"),
    [
        (MockResponse(status=401), EvolvIOTAuthError),
        (MockResponse(payload={}), EvolvIOTAuthError),
    ],
)
async def test_authorization_code_exchange_errors(
    response: MockResponse,
    exception: type[Exception],
) -> None:
    """Test OAuth authorization code exchange errors."""
    api = EvolvIOTApi(cast(ClientSession, MockSession(response)), "https://example.com")

    with pytest.raises(exception):
        await api.async_exchange_authorization_code("code", "id", "secret")


async def test_start_device_authorization() -> None:
    """Test device authorization start."""
    api = EvolvIOTApi(
        cast(ClientSession, MockSession(MockResponse(payload={"device_code": "abc"}))),
        "https://example.com",
    )

    assert await api.async_start_device_authorization() == {"device_code": "abc"}


@pytest.mark.parametrize(
    ("error", "exception"),
    [
        ("authorization_pending", EvolvIOTDeviceAuthorizationPending),
        ("slow_down", EvolvIOTDeviceAuthorizationPending),
        ("access_denied", EvolvIOTDeviceAuthorizationDenied),
        ("expired_token", EvolvIOTDeviceAuthorizationExpired),
        ("invalid_grant", EvolvIOTDeviceAuthorizationExpired),
        ("other", EvolvIOTAuthError),
    ],
)
async def test_device_code_exchange_errors(
    error: str,
    exception: type[Exception],
) -> None:
    """Test device code exchange errors."""
    api = EvolvIOTApi(
        cast(
            ClientSession,
            MockSession(MockResponse(status=400, payload={"error": error})),
        ),
        "https://example.com",
    )

    with pytest.raises(exception):
        await api.async_exchange_device_code("device-code")


async def test_device_code_exchange_success() -> None:
    """Test device code exchange success."""
    api = EvolvIOTApi(
        cast(
            ClientSession, MockSession(MockResponse(payload={"access_token": "token"}))
        ),
        "https://example.com",
    )

    assert await api.async_exchange_device_code("device-code") == {
        "access_token": "token"
    }


async def test_entity_requests_quote_entity_id() -> None:
    """Test entity ID quoting for state and command requests."""
    session = MockSession(MockResponse(payload={}), MockResponse(payload={}))
    api = EvolvIOTApi(cast(ClientSession, session), "https://example.com", "token")

    await api.async_get_state("switch.device/one")
    await api.async_command("switch.device/one", {"command": "turn_on"})

    assert session.request_calls[0][1].endswith("/devices/switch.device%2Fone/state")
    assert session.request_calls[1][1].endswith("/devices/switch.device%2Fone/command")


async def test_request_refreshes_token() -> None:
    """Test token refresh and retry."""
    token_callback = AsyncMock()
    session = MockSession(
        MockResponse(status=401),
        MockResponse(payload={"access_token": "new", "refresh_token": "new-refresh"}),
        MockResponse(payload={"entities": []}),
    )
    api = EvolvIOTApi(
        cast(ClientSession, session),
        "https://example.com",
        "old",
        refresh_token="refresh",
        client_id="client",
        client_secret="secret",
        token_update_callback=token_callback,
    )

    assert await api.async_get_devices() == {"entities": []}
    assert api.access_token == "new"
    token_callback.assert_awaited_once_with(
        {"access_token": "new", "refresh_token": "new-refresh"}
    )


async def test_request_auth_error_without_refresh() -> None:
    """Test request auth error without refresh token."""
    api = EvolvIOTApi(
        cast(ClientSession, MockSession(MockResponse(status=401))),
        "https://example.com",
        "old",
    )

    with pytest.raises(EvolvIOTAuthError):
        await api.async_get_devices()


async def test_request_connection_error() -> None:
    """Test request connection error."""
    api = EvolvIOTApi(cast(ClientSession, ErrorSession()), "https://example.com")

    with pytest.raises(EvolvIOTConnectionError):
        await api.async_get_devices()


async def test_local_command_and_status() -> None:
    """Test local command and status calls."""
    session = MockSession(
        MockResponse(text="ok"),
        MockResponse(payload={"power": 1}),
    )
    api = EvolvIOTApi(cast(ClientSession, session), "https://example.com")

    with patch(
        "homeassistant.components.evolviot.api.os.urandom",
        return_value=b"1" * 16,
    ):
        await api.async_local_command(
            uid="uid",
            device_id="Device_01",
            endpoint="/control",
            device_secret="secret",
            switch_name="power",
            value=1,
        )

    assert session.post_calls[0][0] == "http://evolviot-device-01.local/control"
    assert set(session.post_calls[0][1]["json"]) == {"data", "hmac"}

    assert await api.async_local_status(
        uid="uid",
        device_id="Device_01",
        device_secret="secret",
    ) == {"power": 1}
    assert session.get_calls[0][0] == "http://evolviot-device-01.local/status"


@pytest.fixture(name="client_error_session")
def client_error_session_fixture() -> ErrorSession:
    """Return a session that raises client errors."""
    return ErrorSession()


async def test_local_command_connection_error(
    client_error_session: ErrorSession,
) -> None:
    """Test local command connection errors."""
    api = EvolvIOTApi(cast(ClientSession, client_error_session), "https://example.com")

    with pytest.raises(EvolvIOTConnectionError):
        await api.async_local_command(
            uid="uid",
            device_id="device",
            endpoint="control",
            device_secret="secret",
            switch_name="power",
            value=1,
        )


async def test_local_status_connection_error(
    client_error_session: ErrorSession,
) -> None:
    """Test local status connection errors."""
    api = EvolvIOTApi(cast(ClientSession, client_error_session), "https://example.com")

    with pytest.raises(EvolvIOTConnectionError):
        await api.async_local_status(
            uid="uid",
            device_id="device",
            device_secret="secret",
        )
