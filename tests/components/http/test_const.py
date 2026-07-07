"""Tests for the HTTP const helpers."""

from pathlib import Path
from unittest.mock import MagicMock

from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from homeassistant.components.http.const import (
    KEY_SUPERVISOR_UNIX_SOCKET,
    is_supervisor_unix_socket_request,
)
from homeassistant.helpers.http import KEY_HASS


def _make_request(supervisor_path: Path | None, sockname: str | None) -> web.Request:
    """Build a mocked request with the given supervisor socket configuration."""
    app = web.Application()
    hass = MagicMock()
    hass.http.supervisor_unix_socket_path = supervisor_path
    app[KEY_HASS] = hass
    transport = MagicMock()
    transport.get_extra_info.return_value = sockname
    return make_mocked_request("GET", "/", app=app, transport=transport)


def test_supervisor_unix_socket_request_matches() -> None:
    """Test a request over the Supervisor Unix socket is detected."""
    path = Path("/run/supervisor.sock")
    request = _make_request(path, str(path))
    assert is_supervisor_unix_socket_request(request) is True


def test_supervisor_unix_socket_request_no_path_skips_transport() -> None:
    """Test the transport is not probed when no socket path is configured."""
    request = _make_request(None, "/run/supervisor.sock")
    transport = request.transport
    transport.get_extra_info.reset_mock()
    assert is_supervisor_unix_socket_request(request) is False
    transport.get_extra_info.assert_not_called()


def test_supervisor_unix_socket_request_is_cached() -> None:
    """Test the result is computed once and cached on the request."""
    path = Path("/run/supervisor.sock")
    request = _make_request(path, str(path))
    transport = request.transport
    transport.get_extra_info.reset_mock()
    assert is_supervisor_unix_socket_request(request) is True
    assert is_supervisor_unix_socket_request(request) is True
    transport.get_extra_info.assert_called_once_with("sockname")
    assert request[KEY_SUPERVISOR_UNIX_SOCKET] is True
