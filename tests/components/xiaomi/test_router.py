"""Tests for the xiaomi router client."""

from http import HTTPStatus
from typing import Any

import pytest
import requests
import requests_mock

from homeassistant.components.xiaomi.router import (
    XiaomiAuthError,
    XiaomiClient,
    XiaomiConnectionError,
    XiaomiTimeoutError,
)

LOGIN_URL = "http://192.168.31.1/cgi-bin/luci/api/xqsystem/login"
LIST_URL_TOK1 = "http://192.168.31.1/cgi-bin/luci/;stok=tok1/api/misystem/devicelist"
LIST_URL_TOK2 = "http://192.168.31.1/cgi-bin/luci/;stok=tok2/api/misystem/devicelist"

DEVICE_LIST: list[dict[str, Any]] = [
    {
        "mac": "AA:BB:CC:DD:EE:FF",
        "name": "my-phone",
        "online": 1,
        "ip": [{"ip": "192.168.31.10"}],
    },
    {
        "mac": "11:22:33:44:55:66",
        "name": "my-laptop",
        "online": 0,
        "ip": [{"ip": "192.168.31.11"}],
    },
]


def _client(token: str | None = None) -> XiaomiClient:
    """Create a client for the mocked router, optionally with a token."""
    client = XiaomiClient("192.168.31.1", "admin", "password")
    client.token = token
    return client


LOGIN_FAILURES: list[tuple[dict[str, Any], type[Exception]]] = [
    ({"exc": requests.exceptions.Timeout()}, XiaomiTimeoutError),
    ({"exc": requests.exceptions.ConnectionError()}, XiaomiConnectionError),
    ({"status_code": HTTPStatus.UNAUTHORIZED}, XiaomiAuthError),
    ({"status_code": HTTPStatus.INTERNAL_SERVER_ERROR}, XiaomiConnectionError),
    ({"text": "not json"}, XiaomiConnectionError),
    ({"json": ["token"]}, XiaomiConnectionError),
    ({"json": {"code": 1008}}, XiaomiAuthError),
    ({"json": {"token": None}}, XiaomiAuthError),
]


def test_login_success(requests_mock: requests_mock.Mocker) -> None:
    """Test a successful login stores the token."""
    requests_mock.post(LOGIN_URL, json={"token": "tok1"})

    client = _client()
    client.login()

    assert client.token == "tok1"
    assert requests_mock.last_request is not None
    assert "username=admin" in requests_mock.last_request.text
    assert "password=password" in requests_mock.last_request.text


@pytest.mark.parametrize(
    ("response_config", "expected"),
    LOGIN_FAILURES,
    ids=[
        "timeout",
        "connection_error",
        "http_401",
        "http_500",
        "invalid_json",
        "json_array",
        "no_token",
        "null_token",
    ],
)
def test_login_failure(
    requests_mock: requests_mock.Mocker,
    response_config: dict[str, Any],
    expected: type[Exception],
) -> None:
    """Test login failures are mapped to the integration error types."""
    requests_mock.post(LOGIN_URL, **response_config)

    client = _client()

    with pytest.raises(expected):
        client.login()


def test_login_invalid_url(requests_mock: requests_mock.Mocker) -> None:
    """Test an invalid URL from user input is converted to a connection error."""
    with pytest.raises(XiaomiConnectionError):
        XiaomiClient("[192.168.31.1", "admin", "password").login()


def test_get_device_list_success(requests_mock: requests_mock.Mocker) -> None:
    """Test the device list is returned without re-logging in."""
    requests_mock.get(LIST_URL_TOK1, json={"code": 0, "list": DEVICE_LIST})

    client = _client("tok1")
    assert client.get_device_list() == DEVICE_LIST
    assert client.token == "tok1"
    assert requests_mock.last_request is not None
    assert requests_mock.last_request.method == "GET"


def test_get_device_list_logs_in_when_no_token(
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test the client logs in before the first device list request."""
    requests_mock.post(LOGIN_URL, json={"token": "tok1"})
    requests_mock.get(LIST_URL_TOK1, json={"code": 0, "list": DEVICE_LIST})

    client = _client()
    assert client.get_device_list() == DEVICE_LIST
    assert client.token == "tok1"


@pytest.mark.parametrize(
    "first_response",
    [{"json": {"code": 1008}}, {"status_code": HTTPStatus.UNAUTHORIZED}],
    ids=["wrong_xiaomi_code", "http_401"],
)
def test_get_device_list_retries_with_refreshed_token(
    requests_mock: requests_mock.Mocker,
    first_response: dict[str, Any],
) -> None:
    """Test an expired token is refreshed once and the list request retried."""
    requests_mock.get(LIST_URL_TOK1, **first_response)
    requests_mock.post(LOGIN_URL, json={"token": "tok2"})
    requests_mock.get(LIST_URL_TOK2, json={"code": 0, "list": DEVICE_LIST})

    client = _client("tok1")
    assert client.get_device_list() == DEVICE_LIST
    assert client.token == "tok2"


def test_get_device_list_auth_failure_propagates(
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test an auth failure on the re-login propagates instead of retrying."""
    requests_mock.get(LIST_URL_TOK1, json={"code": 1008})
    requests_mock.post(LOGIN_URL, status_code=HTTPStatus.UNAUTHORIZED)

    client = _client("tok1")

    with pytest.raises(XiaomiAuthError):
        client.get_device_list()


LIST_FAILURES: list[tuple[dict[str, Any], type[Exception]]] = [
    ({"exc": requests.exceptions.Timeout()}, XiaomiTimeoutError),
    ({"exc": requests.exceptions.ConnectionError()}, XiaomiConnectionError),
    ({"status_code": HTTPStatus.INTERNAL_SERVER_ERROR}, XiaomiConnectionError),
    ({"text": "not json"}, XiaomiConnectionError),
    ({"json": {}}, XiaomiConnectionError),
    ({"json": {"code": 0}}, XiaomiConnectionError),
    ({"json": [0, 1]}, XiaomiConnectionError),
    ({"json": {"code": 0, "list": "nope"}}, XiaomiConnectionError),
]


@pytest.mark.parametrize(
    ("response_config", "expected"),
    LIST_FAILURES,
    ids=[
        "timeout",
        "connection_error",
        "http_500",
        "invalid_json",
        "missing_code",
        "missing_list",
        "json_array",
        "list_not_a_list",
    ],
)
def test_get_device_list_failure(
    requests_mock: requests_mock.Mocker,
    response_config: dict[str, Any],
    expected: type[Exception],
) -> None:
    """Test non-auth list failures are mapped to the integration error types."""
    requests_mock.get(LIST_URL_TOK1, **response_config)

    client = _client("tok1")

    with pytest.raises(expected):
        client.get_device_list()

    # Connection-class failures must not trigger a re-login.
    assert all(req.method == "GET" for req in requests_mock.request_history)


def test_get_device_list_filters_non_dict_entries(
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test malformed entries are dropped instead of escaping the client."""
    requests_mock.get(
        LIST_URL_TOK1,
        json={"code": 0, "list": [DEVICE_LIST[0], "junk", None]},
    )

    client = _client("tok1")
    assert client.get_device_list() == [DEVICE_LIST[0]]
