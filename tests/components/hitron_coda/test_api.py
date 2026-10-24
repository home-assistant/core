"""Test the router's HTTP protocol and session handling."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import requests

from homeassistant.components.hitron_coda import api

HOST = "192.0.2.1"
MAC = "AA:BB:CC:DD:EE:FF"


def response(
    status: int = 200, payload: object = None, cookies: dict[str, str] | None = None
) -> MagicMock:
    """Build a context-managed HTTP response."""
    result = MagicMock(spec=requests.Response)
    result.status_code = status
    result.cookies = cookies or {}
    result.json.return_value = payload
    result.__enter__.return_value = result
    return result


@pytest.fixture
def mock_requests() -> Generator[tuple[MagicMock, MagicMock]]:
    """Mock transport calls while exercising the real client."""
    with (
        patch.object(api.requests, "post") as post,
        patch.object(api.requests, "get") as get,
    ):
        post.return_value = response(cookies={"userid": "session"})
        get.return_value = response(
            payload=[{"macAddr": MAC.lower(), "hostName": "phone"}]
        )
        yield post, get


@pytest.mark.parametrize(
    ("router_type", "password_field"),
    [
        pytest.param("rogers", "pws", id="rogers"),
        pytest.param("shaw", "pwd", id="shaw"),
    ],
)
def test_login_and_fetch(
    mock_requests: tuple[MagicMock, MagicMock], router_type: str, password_field: str
) -> None:
    """Preserve the two providers' login formats and the session cookie."""
    post, get = mock_requests
    client = api.HitronCodaClient(HOST, "admin", "secret", router_type)
    post.assert_not_called()
    assert client.get_devices() == {MAC: "phone"}
    post.assert_called_once_with(
        f"http://{HOST}/goform/login",
        data={"user": "admin", password_field: "secret"},
        timeout=10,
    )
    get.assert_called_once_with(
        f"http://{HOST}/data/getConnectInfo.asp",
        cookies={"userid": "session"},
        timeout=10,
    )


def test_reuse_session(mock_requests: tuple[MagicMock, MagicMock]) -> None:
    """Do not log in again on each poll."""
    post, get = mock_requests
    client = api.HitronCodaClient(HOST, "admin", "secret", "rogers")
    assert client.get_devices() == {MAC: "phone"}
    assert client.get_devices() == {MAC: "phone"}
    assert post.call_count == 1
    assert get.call_count == 2


def test_expired_session(mock_requests: tuple[MagicMock, MagicMock]) -> None:
    """Retry an expired session with the refreshed cookie."""
    post, get = mock_requests
    post.side_effect = [
        response(cookies={"userid": "old-session"}),
        response(cookies={"userid": "new-session"}),
    ]
    get.side_effect = [response(status=401), response(payload=[])]
    client = api.HitronCodaClient(HOST, "admin", "secret", "rogers")
    assert client.get_devices() == {}
    assert post.call_count == 2
    assert get.call_args.kwargs["cookies"] == {"userid": "new-session"}


def test_session_retry_is_bounded(mock_requests: tuple[MagicMock, MagicMock]) -> None:
    """Do not repeatedly authenticate when the router keeps rejecting the session."""
    post, get = mock_requests
    get.return_value = response(status=403)
    with pytest.raises(api.InvalidAuth, match="session"):
        api.HitronCodaClient(HOST, "admin", "secret", "rogers").get_devices()
    assert post.call_count == 2
    assert get.call_count == 2


@pytest.mark.parametrize("status", [401, 403])
def test_invalid_credentials(
    mock_requests: tuple[MagicMock, MagicMock], status: int
) -> None:
    """Report rejected credentials separately from connection failures."""
    post, get = mock_requests
    post.return_value = response(status=status)
    with pytest.raises(api.InvalidAuth, match="credentials"):
        api.HitronCodaClient(HOST, "admin", "secret", "rogers").get_devices()
    get.assert_not_called()


def test_missing_cookie(mock_requests: tuple[MagicMock, MagicMock]) -> None:
    """A successful HTTP response without a session means login failed."""
    post, get = mock_requests
    post.return_value = response()
    with pytest.raises(api.InvalidAuth, match="session cookie"):
        api.HitronCodaClient(HOST, "admin", "secret", "rogers").get_devices()
    get.assert_not_called()


@pytest.mark.parametrize("request_index", [0, 1], ids=["login", "devices"])
@pytest.mark.parametrize(
    "error",
    [requests.Timeout(), requests.ConnectionError()],
    ids=["timeout", "connection"],
)
def test_transport_error(
    mock_requests: tuple[MagicMock, MagicMock], request_index: int, error: Exception
) -> None:
    """Translate transport errors into an update/setup failure."""
    mock_requests[request_index].side_effect = error
    with pytest.raises(api.CannotConnect, match="router"):
        api.HitronCodaClient(HOST, "admin", "secret", "rogers").get_devices()


@pytest.mark.parametrize("request_index", [0, 1], ids=["login", "devices"])
def test_http_error(
    mock_requests: tuple[MagicMock, MagicMock], request_index: int
) -> None:
    """Reject failed HTTP requests instead of marking clients disconnected."""
    mock_requests[request_index].return_value = response(status=503)
    with pytest.raises(api.CannotConnect, match="503"):
        api.HitronCodaClient(HOST, "admin", "secret", "rogers").get_devices()


def test_invalid_json(mock_requests: tuple[MagicMock, MagicMock]) -> None:
    """A malformed response must not become an empty device list."""
    _, get = mock_requests
    get.return_value.json.side_effect = ValueError("invalid JSON")
    with pytest.raises(api.CannotConnect, match="Invalid JSON"):
        api.HitronCodaClient(HOST, "admin", "secret", "rogers").get_devices()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="not-a-list"),
        pytest.param([None], id="not-a-device"),
        pytest.param([{"macAddr": 1}], id="invalid-mac"),
        pytest.param([{"macAddr": MAC, "hostName": []}], id="invalid-hostname"),
    ],
)
def test_invalid_device_data(
    mock_requests: tuple[MagicMock, MagicMock], payload: object
) -> None:
    """Reject malformed device data without corrupting the last successful poll."""
    _, get = mock_requests
    get.return_value = response(payload=payload)
    with pytest.raises(api.CannotConnect, match="Invalid device"):
        api.HitronCodaClient(HOST, "admin", "secret", "rogers").get_devices()


def test_skip_missing_mac(mock_requests: tuple[MagicMock, MagicMock]) -> None:
    """Skip unidentifiable clients and accept clients without a hostname."""
    _, get = mock_requests
    get.return_value = response(
        payload=[{"macAddr": None, "hostName": "unknown"}, {"macAddr": MAC}]
    )
    assert api.HitronCodaClient(HOST, "admin", "secret", "rogers").get_devices() == {
        MAC: None
    }


def test_empty_scan(mock_requests: tuple[MagicMock, MagicMock]) -> None:
    """An empty successful scan means no clients are currently connected."""
    _, get = mock_requests
    get.return_value = response(payload=[])
    assert api.HitronCodaClient(HOST, "admin", "secret", "rogers").get_devices() == {}
