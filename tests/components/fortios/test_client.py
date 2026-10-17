"""Test FortiOS parsing and transport using the published async library."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiofortiosapi import FortiOSAuthenticationError, FortiOSError, FortiOSResponseError
import pytest

from homeassistant.components.fortios.client import FortiOSClient, UnsupportedVersion
from homeassistant.core import HomeAssistant

from .conftest import MAC, SERIAL, USER_INPUT


@pytest.fixture
def mock_response() -> Generator[MagicMock]:
    """Mock HTTP while executing the real library's request and parsing code."""
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value={"version": "v7.6.0", "serial": SERIAL})
    response.text = AsyncMock(return_value="Server error")
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    with patch("aiohttp.ClientSession.request", return_value=context) as request:
        response.request = request
        yield response


@pytest.mark.parametrize("status", [401, 403])
async def test_invalid_auth(
    hass: HomeAssistant, mock_response: MagicMock, status: int
) -> None:
    """Map unauthorized HTTP responses to authentication errors."""
    mock_response.status = status
    with pytest.raises(FortiOSAuthenticationError):
        await FortiOSClient(hass, USER_INPUT).connect()


@pytest.mark.parametrize("version", ["v6.4.3", "v7.6.0"])
async def test_connect_and_scan(
    hass: HomeAssistant, mock_response: MagicMock, version: str
) -> None:
    """Normalize legacy master MACs and ignore clients without an identity."""
    mock_response.json.return_value = {"version": version, "serial": SERIAL}
    client = FortiOSClient(hass, USER_INPUT)
    assert await client.connect() == SERIAL
    mock_response.request.reset_mock()
    mock_response.json.return_value = {
        "results": [
            {"master_mac": MAC.lower(), "hostname": "phone", "is_online": True},
            {"hostname": "missing-mac"},
        ]
    }
    devices = await client.update()
    assert list(devices) == [MAC]
    assert devices[MAC].hostname == "phone"
    assert devices[MAC].online
    mock_response.request.assert_called_once_with(
        "GET",
        "https://192.168.1.1:443/api/v2/monitor/user/device/query",
        headers={"Authorization": "Bearer test-token"},
        params={"filter": "format=master_mac|hostname|is_online", "vdom": "root"},
        ssl=True,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"version": "v7.6.0"},
        {"serial": SERIAL},
        {"serial": SERIAL, "version": "invalid"},
        None,
        {"status": "error"},
    ],
)
async def test_invalid_identity(
    hass: HomeAssistant, mock_response: MagicMock, payload: dict[str, str] | None
) -> None:
    """Invalid identities cannot become a unique ID or bypass firmware validation."""
    mock_response.json.return_value = payload
    with pytest.raises(FortiOSResponseError):
        await FortiOSClient(hass, USER_INPUT).connect()


async def test_unsupported_firmware(
    hass: HomeAssistant, mock_response: MagicMock
) -> None:
    """Reject unsupported firmware at configuration time."""
    mock_response.json.return_value = {"version": "v6.4.2", "serial": SERIAL}
    with pytest.raises(UnsupportedVersion):
        await FortiOSClient(hass, USER_INPUT).connect()


@pytest.mark.parametrize("status", [404, 500])
async def test_http_failure(
    hass: HomeAssistant, mock_response: MagicMock, status: int
) -> None:
    """Surface HTTP endpoint and server errors from the library."""

    mock_response.status = status
    with pytest.raises(FortiOSError):
        await FortiOSClient(hass, USER_INPUT).connect()


@pytest.mark.parametrize(
    "payload",
    [{"results": None}, {"results": {}}, {"results": [None]}, {"status": "error"}],
)
async def test_invalid_scan(
    hass: HomeAssistant, mock_response: MagicMock, payload: dict[str, object]
) -> None:
    """Malformed responses are failures rather than a successful empty scan."""
    mock_response.json.return_value = payload
    with pytest.raises(FortiOSResponseError):
        await FortiOSClient(hass, USER_INPUT).update()


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        (
            "fortigate.local:8443",
            "https://fortigate.local:8443/api/v2/monitor/system/status",
        ),
        (
            "[2001:db8::1]:8443",
            "https://[2001:db8::1]:8443/api/v2/monitor/system/status",
        ),
    ],
)
async def test_custom_port(
    hass: HomeAssistant, mock_response: MagicMock, host: str, expected: str
) -> None:
    """Preserve host:port YAML support and bracket IPv6 addresses."""
    await FortiOSClient(hass, USER_INPUT | {"host": host}).connect()
    assert str(mock_response.request.call_args.args[1]) == expected


@pytest.mark.parametrize(
    "host",
    ["host:bad", "host/path", "user:pass@host", "host?token=secret", "", "[broken"],
)
async def test_invalid_host(hass: HomeAssistant, host: str) -> None:
    """Reject inputs that are not hostnames or addresses with an optional port."""
    with pytest.raises(FortiOSResponseError):
        FortiOSClient(hass, USER_INPUT | {"host": host})


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_error_envelope(
    hass: HomeAssistant, mock_response: MagicMock, status: int
) -> None:
    """A successful HTTP response may still carry an authentication failure envelope."""
    mock_response.json.return_value = {"status": "error", "http_status": status}
    with pytest.raises(FortiOSAuthenticationError):
        await FortiOSClient(hass, USER_INPUT).connect()
