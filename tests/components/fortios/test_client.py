"""Test the synchronous library adapter against FortiOS HTTP responses."""

import json
from unittest.mock import MagicMock, patch

from fortiosapi import NotLogged
import pytest
from requests import Response
from requests.exceptions import HTTPError, RequestException

from homeassistant.components.fortios.client import FortiOSClient, UnsupportedVersion

from .conftest import MAC, SERIAL, USER_INPUT


def response(payload: dict, status: int = 200) -> MagicMock:
    """Build a response handled by the real library parser."""
    result = MagicMock(spec=Response)
    result.status_code = status
    result.content = json.dumps(payload).encode()
    result.headers = {"content-type": "application/json"}
    result.request = MagicMock()
    if status >= 400:
        result.raise_for_status.side_effect = HTTPError
    return result


@pytest.mark.parametrize("status", [401, 403])
def test_invalid_auth(status: int) -> None:
    """Reject unauthorized responses before the library tries to read a version."""
    with patch("fortiosapi.fortiosapi.requests.session") as session:
        session.return_value.get.return_value = response({"status": "error"}, status)
        client = FortiOSClient(USER_INPUT)
        with pytest.raises(NotLogged):
            client.connect()
        client.close()
        session.return_value.close.assert_called_once()
        session.return_value.post.assert_not_called()


@pytest.mark.parametrize("version", ["v6.4.3", "v7.6.0"])
def test_connect_and_scan(version: str) -> None:
    """Validate firmware and normalize clients with one shared scan."""
    with patch("fortiosapi.fortiosapi.requests.session") as session:
        session.return_value.get.return_value = response(
            {"version": version, "serial": SERIAL}
        )
        client = FortiOSClient(USER_INPUT)
        assert client.connect() == SERIAL
        session.return_value.get.reset_mock()
        session.return_value.get.return_value = response(
            {
                "results": [
                    {"master_mac": MAC.lower(), "hostname": "phone", "is_online": True},
                    {"hostname": "missing-mac"},
                ]
            }
        )
        devices = client.update()
        assert list(devices) == [MAC]
        assert devices[MAC].hostname == "phone"
        assert devices[MAC].online
        session.return_value.get.assert_called_once()
        client.close()


def test_unsupported_firmware() -> None:
    """Reject unsupported firmware at configuration time."""
    with patch("fortiosapi.fortiosapi.requests.session") as session:
        session.return_value.get.return_value = response(
            {"version": "v6.4.2", "serial": SERIAL}
        )
        client = FortiOSClient(USER_INPUT)
        with pytest.raises(UnsupportedVersion):
            client.connect()
        client.close()


def test_http_failure() -> None:
    """Surface HTTP failures before parsing incomplete responses."""
    with patch("fortiosapi.fortiosapi.requests.session") as session:
        session.return_value.get.return_value = response({"status": "error"}, 500)
        client = FortiOSClient(USER_INPUT)
        with pytest.raises(RequestException):
            client.connect()
        client.close()
