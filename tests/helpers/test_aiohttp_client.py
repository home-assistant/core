"""Test the aiohttp client helper."""

from collections.abc import AsyncGenerator
import socket
from unittest.mock import Mock, patch

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

from homeassistant.components.mjpeg import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    DOMAIN as MJPEG_DOMAIN,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_CLOSE,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client as client
from homeassistant.util import ssl as ssl_util
from homeassistant.util.color import RGBColor
from homeassistant.util.ssl import SSLCipherList

from tests.common import (
    MockConfigEntry,
    MockModule,
    extract_stack_to_frame,
    mock_integration,
)
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture(name="camera_client")
async def camera_client_fixture(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> TestClient:
    """Fixture to fetch camera streams."""
    mock_config_entry = MockConfigEntry(
        title="MJPEG Camera",
        domain=MJPEG_DOMAIN,
        options={
            CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
            CONF_MJPEG_URL: "http://example.com/mjpeg_stream",
            CONF_PASSWORD: None,
            CONF_STILL_IMAGE_URL: None,
            CONF_USERNAME: None,
            CONF_VERIFY_SSL: True,
        },
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return await hass_client()


async def test_get_clientsession_with_ssl(hass: HomeAssistant) -> None:
    """Test init clientsession with ssl."""
    client.async_get_clientsession(hass)
    verify_ssl = True
    ssl_cipher = SSLCipherList.PYTHON_DEFAULT
    family = 0

    client_session = hass.data[client.DATA_CLIENTSESSION][
        (verify_ssl, family, ssl_cipher)
    ]
    assert isinstance(client_session, aiohttp.ClientSession)
    connector = hass.data[client.DATA_CONNECTOR][(verify_ssl, family, ssl_cipher)]
    assert isinstance(connector, aiohttp.TCPConnector)


async def test_get_clientsession_without_ssl(hass: HomeAssistant) -> None:
    """Test init clientsession without ssl."""
    client.async_get_clientsession(hass, verify_ssl=False)
    verify_ssl = False
    ssl_cipher = SSLCipherList.PYTHON_DEFAULT
    family = 0

    client_session = hass.data[client.DATA_CLIENTSESSION][
        (verify_ssl, family, ssl_cipher)
    ]
    assert isinstance(client_session, aiohttp.ClientSession)
    connector = hass.data[client.DATA_CONNECTOR][(verify_ssl, family, ssl_cipher)]
    assert isinstance(connector, aiohttp.TCPConnector)


@pytest.mark.parametrize(
    ("verify_ssl", "expected_family", "ssl_cipher"),
    [
        (True, socket.AF_UNSPEC, SSLCipherList.PYTHON_DEFAULT),
        (True, socket.AF_INET, SSLCipherList.PYTHON_DEFAULT),
        (True, socket.AF_INET6, SSLCipherList.PYTHON_DEFAULT),
        (True, socket.AF_UNSPEC, SSLCipherList.INTERMEDIATE),
        (True, socket.AF_INET, SSLCipherList.INTERMEDIATE),
        (True, socket.AF_INET6, SSLCipherList.INTERMEDIATE),
        (True, socket.AF_UNSPEC, SSLCipherList.MODERN),
        (True, socket.AF_INET, SSLCipherList.MODERN),
        (True, socket.AF_INET6, SSLCipherList.MODERN),
        (True, socket.AF_UNSPEC, SSLCipherList.INSECURE),
        (True, socket.AF_INET, SSLCipherList.INSECURE),
        (True, socket.AF_INET6, SSLCipherList.INSECURE),
        (False, socket.AF_UNSPEC, SSLCipherList.PYTHON_DEFAULT),
        (False, socket.AF_INET, SSLCipherList.PYTHON_DEFAULT),
        (False, socket.AF_INET6, SSLCipherList.PYTHON_DEFAULT),
        (False, socket.AF_UNSPEC, SSLCipherList.INTERMEDIATE),
        (False, socket.AF_INET, SSLCipherList.INTERMEDIATE),
        (False, socket.AF_INET6, SSLCipherList.INTERMEDIATE),
        (False, socket.AF_UNSPEC, SSLCipherList.MODERN),
        (False, socket.AF_INET, SSLCipherList.MODERN),
        (False, socket.AF_INET6, SSLCipherList.MODERN),
        (False, socket.AF_UNSPEC, SSLCipherList.INSECURE),
        (False, socket.AF_INET, SSLCipherList.INSECURE),
        (False, socket.AF_INET6, SSLCipherList.INSECURE),
    ],
)
async def test_get_clientsession(
    hass: HomeAssistant,
    verify_ssl: bool,
    expected_family: int,
    ssl_cipher: SSLCipherList,
) -> None:
    """Test init clientsession combinations."""
    client.async_get_clientsession(
        hass, verify_ssl=verify_ssl, family=expected_family, ssl_cipher=ssl_cipher
    )
    client_session = hass.data[client.DATA_CLIENTSESSION][
        (verify_ssl, expected_family, ssl_cipher)
    ]
    assert isinstance(client_session, aiohttp.ClientSession)
    connector = hass.data[client.DATA_CONNECTOR][
        (verify_ssl, expected_family, ssl_cipher)
    ]
    assert isinstance(connector, aiohttp.TCPConnector)


async def test_create_clientsession_with_ssl_and_cookies(hass: HomeAssistant) -> None:
    """Test create clientsession with ssl."""
    session = client.async_create_clientsession(hass, cookies={"bla": True})
    assert isinstance(session, aiohttp.ClientSession)

    verify_ssl = True
    ssl_cipher = SSLCipherList.PYTHON_DEFAULT
    family = 0

    assert client.DATA_CLIENTSESSION not in hass.data
    connector = hass.data[client.DATA_CONNECTOR][(verify_ssl, family, ssl_cipher)]
    assert isinstance(connector, aiohttp.TCPConnector)


async def test_create_clientsession_without_ssl_and_cookies(
    hass: HomeAssistant,
) -> None:
    """Test create clientsession without ssl."""
    session = client.async_create_clientsession(hass, False, cookies={"bla": True})
    assert isinstance(session, aiohttp.ClientSession)

    verify_ssl = False
    ssl_cipher = SSLCipherList.PYTHON_DEFAULT
    family = 0

    assert client.DATA_CLIENTSESSION not in hass.data
    connector = hass.data[client.DATA_CONNECTOR][(verify_ssl, family, ssl_cipher)]
    assert isinstance(connector, aiohttp.TCPConnector)


@pytest.mark.parametrize(
    ("verify_ssl", "expected_family", "ssl_cipher"),
    [
        (True, 0, SSLCipherList.PYTHON_DEFAULT),
        (True, 4, SSLCipherList.PYTHON_DEFAULT),
        (True, 6, SSLCipherList.PYTHON_DEFAULT),
        (True, 0, SSLCipherList.INTERMEDIATE),
        (True, 4, SSLCipherList.INTERMEDIATE),
        (True, 6, SSLCipherList.INTERMEDIATE),
        (True, 0, SSLCipherList.MODERN),
        (True, 4, SSLCipherList.MODERN),
        (True, 6, SSLCipherList.MODERN),
        (True, 0, SSLCipherList.INSECURE),
        (True, 4, SSLCipherList.INSECURE),
        (True, 6, SSLCipherList.INSECURE),
        (False, 0, SSLCipherList.PYTHON_DEFAULT),
        (False, 4, SSLCipherList.PYTHON_DEFAULT),
        (False, 6, SSLCipherList.PYTHON_DEFAULT),
        (False, 0, SSLCipherList.INTERMEDIATE),
        (False, 4, SSLCipherList.INTERMEDIATE),
        (False, 6, SSLCipherList.INTERMEDIATE),
        (False, 0, SSLCipherList.MODERN),
        (False, 4, SSLCipherList.MODERN),
        (False, 6, SSLCipherList.MODERN),
        (False, 0, SSLCipherList.INSECURE),
        (False, 4, SSLCipherList.INSECURE),
        (False, 6, SSLCipherList.INSECURE),
    ],
)
async def test_get_clientsession_cleanup(
    hass: HomeAssistant,
    verify_ssl: bool,
    expected_family: int,
    ssl_cipher: SSLCipherList,
) -> None:
    """Test init clientsession cleanup."""
    client.async_get_clientsession(
        hass, verify_ssl=verify_ssl, family=expected_family, ssl_cipher=ssl_cipher
    )

    client_session = hass.data[client.DATA_CLIENTSESSION][
        (verify_ssl, expected_family, ssl_cipher)
    ]
    assert isinstance(client_session, aiohttp.ClientSession)
    connector = hass.data[client.DATA_CONNECTOR][
        (verify_ssl, expected_family, ssl_cipher)
    ]
    assert isinstance(connector, aiohttp.TCPConnector)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert client_session.closed
    assert connector.closed


async def test_get_clientsession_patched_close(hass: HomeAssistant) -> None:
    """Test closing clientsession does not work."""

    verify_ssl = True
    ssl_cipher = SSLCipherList.PYTHON_DEFAULT
    family = 0

    with patch("aiohttp.ClientSession.close") as mock_close:
        session = client.async_get_clientsession(hass)

        assert isinstance(
            hass.data[client.DATA_CLIENTSESSION][(verify_ssl, family, ssl_cipher)],
            aiohttp.ClientSession,
        )
        assert isinstance(
            hass.data[client.DATA_CONNECTOR][(verify_ssl, family, ssl_cipher)],
            aiohttp.TCPConnector,
        )

        with pytest.raises(RuntimeError):
            await session.close()

        assert mock_close.call_count == 0


async def test_warning_close_session_integration(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test log warning message when closing the session from integration context."""
    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.close()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/paulus/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    Mock(
                        filename="/home/paulus/homeassistant/components/hue/light.py",
                        lineno="23",
                        line="await session.close()",
                    ),
                    Mock(
                        filename="/home/paulus/aiohue/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        session = client.async_get_clientsession(hass)
        await session.close()
    assert (
        "Detected that integration 'hue' closes the Home Assistant aiohttp session at "
        "homeassistant/components/hue/light.py, line 23: await session.close(). "
        "Please create a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22"
    ) in caplog.text


async def test_warning_close_session_custom(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test log warning message when closing the session from custom context."""
    mock_integration(hass, MockModule("hue"), built_in=False)
    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.close()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/paulus/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    Mock(
                        filename="/home/paulus/config/custom_components/hue/light.py",
                        lineno="23",
                        line="await session.close()",
                    ),
                    Mock(
                        filename="/home/paulus/aiohue/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        session = client.async_get_clientsession(hass)
        await session.close()
    assert (
        "Detected that custom integration 'hue' closes the Home Assistant aiohttp "
        "session at custom_components/hue/light.py, line 23: await session.close(). "
        "Please report it to the author of the 'hue' custom integration"
    ) in caplog.text


async def test_async_aiohttp_proxy_stream(
    aioclient_mock: AiohttpClientMocker, camera_client: TestClient
) -> None:
    """Test that it fetches the given url."""
    aioclient_mock.get("http://example.com/mjpeg_stream", content=b"Frame1Frame2Frame3")

    resp = await camera_client.get("/api/camera_proxy_stream/camera.mjpeg_camera")

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = await resp.text()
    assert body == "Frame1Frame2Frame3"


async def test_async_aiohttp_proxy_stream_timeout(
    aioclient_mock: AiohttpClientMocker, camera_client: TestClient
) -> None:
    """Test that it fetches the given url."""
    aioclient_mock.get("http://example.com/mjpeg_stream", exc=TimeoutError())

    resp = await camera_client.get("/api/camera_proxy_stream/camera.mjpeg_camera")
    assert resp.status == 504


async def test_async_aiohttp_proxy_stream_client_err(
    aioclient_mock: AiohttpClientMocker, camera_client: TestClient
) -> None:
    """Test that it fetches the given url."""
    aioclient_mock.get("http://example.com/mjpeg_stream", exc=aiohttp.ClientError())

    resp = await camera_client.get("/api/camera_proxy_stream/camera.mjpeg_camera")
    assert resp.status == 502


async def test_sending_named_tuple(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test sending a named tuple in json."""
    resp = aioclient_mock.post("http://127.0.0.1/rgb", json={"rgb": RGBColor(4, 3, 2)})
    session = client.async_create_clientsession(hass)
    resp = await session.post("http://127.0.0.1/rgb", json={"rgb": RGBColor(4, 3, 2)})
    assert resp.status == 200
    assert await resp.json() == {"rgb": [4, 3, 2]}
    assert aioclient_mock.mock_calls[0][2]["rgb"] == RGBColor(4, 3, 2)


async def test_client_session_immutable_headers(hass: HomeAssistant) -> None:
    """Test we can't mutate headers."""
    session = client.async_get_clientsession(hass)

    with pytest.raises(TypeError):
        session.headers["user-agent"] = "bla"

    with pytest.raises(AttributeError):
        session.headers.update({"user-agent": "bla"})


@pytest.mark.usefixtures("disable_mock_zeroconf_resolver")
@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_async_mdnsresolver(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test async_mdnsresolver."""
    resp = aioclient_mock.post("http://localhost/xyz", json={"x": 1})
    session = client.async_create_clientsession(hass)
    resp = await session.post("http://localhost/xyz", json={"x": 1})
    assert resp.status == 200
    assert await resp.json() == {"x": 1}


async def test_resolver_is_singleton(hass: HomeAssistant) -> None:
    """Test that the resolver is a singleton."""
    session = client.async_get_clientsession(hass)
    session2 = client.async_get_clientsession(hass)
    session3 = client.async_create_clientsession(hass)
    assert isinstance(session._connector, aiohttp.TCPConnector)
    assert isinstance(session2._connector, aiohttp.TCPConnector)
    assert isinstance(session3._connector, aiohttp.TCPConnector)
    assert session._connector._resolver is session2._connector._resolver
    assert session._connector._resolver is session3._connector._resolver


async def test_connector_uses_http11_alpn(hass: HomeAssistant) -> None:
    """Test that connector uses HTTP/1.1 ALPN protocols."""
    with patch.object(
        ssl_util, "client_context", wraps=ssl_util.client_context
    ) as mock_client_context:
        client.async_get_clientsession(hass)

        # Verify client_context was called with HTTP/1.1 ALPN
        mock_client_context.assert_called_once_with(
            SSLCipherList.PYTHON_DEFAULT, ssl_util.SSL_ALPN_HTTP11
        )


async def test_connector_no_verify_uses_http11_alpn(hass: HomeAssistant) -> None:
    """Test that connector without SSL verification uses HTTP/1.1 ALPN protocols."""
    with patch.object(
        ssl_util, "client_context_no_verify", wraps=ssl_util.client_context_no_verify
    ) as mock_client_context_no_verify:
        client.async_get_clientsession(hass, verify_ssl=False)

        # Verify client_context_no_verify was called with HTTP/1.1 ALPN
        mock_client_context_no_verify.assert_called_once_with(
            SSLCipherList.PYTHON_DEFAULT, ssl_util.SSL_ALPN_HTTP11
        )


@pytest.fixture
async def redirect_server() -> AsyncGenerator[TestServer]:
    """Start a test server that redirects based on query parameters."""

    async def handle_redirect(request: web.Request) -> web.Response:
        """Redirect to the URL specified in the 'to' query parameter."""
        location = request.query["to"]
        return web.Response(status=307, headers={"Location": location})

    async def handle_ok(request: web.Request) -> web.Response:
        """Return a 200 OK response."""
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/redirect", handle_redirect)
    app.router.add_get("/ok", handle_ok)

    async def _mock_resolve_host(
        self: aiohttp.TCPConnector,
        host: str,
        port: int,
        traces: object = None,
    ) -> list[dict[str, object]]:
        return [
            {
                "hostname": host,
                "host": "127.0.0.1",
                "port": port,
                "family": socket.AF_INET,
                "proto": 6,
                "flags": 0,
            }
        ]

    server = TestServer(app)
    await server.start_server()
    # Route all TCP connections to the local test server
    # This allows us to test redirect behavior of external URLs
    # without actually making network requests
    with patch.object(aiohttp.TCPConnector, "_resolve_host", _mock_resolve_host):
        yield server
    await server.close()


def _resolve_result(host: str, addr: str) -> list[dict[str, object]]:
    """Build a mock DNS resolve result for the SSRF check."""
    return [
        {
            "hostname": host,
            "host": addr,
            "port": 0,
            "family": socket.AF_INET,
            "proto": 6,
            "flags": 0,
        }
    ]


@pytest.mark.usefixtures("socket_enabled")
async def test_redirect_loopback_to_loopback_allowed(
    hass: HomeAssistant, redirect_server: TestServer
) -> None:
    """Test that redirects from loopback to loopback are allowed."""
    session = client.async_get_clientsession(hass)
    target = str(redirect_server.make_url("/ok"))
    redirect_url = redirect_server.make_url(f"/redirect?to={target}")

    # Both origin and target are on 127.0.0.1 — should be allowed
    resp = await session.get(redirect_url)
    assert resp.status == 200


@pytest.mark.usefixtures("socket_enabled")
async def test_redirect_relative_url_allowed(
    hass: HomeAssistant, redirect_server: TestServer
) -> None:
    """Test that relative redirects are allowed (they stay on the same host)."""
    session = client.async_create_clientsession(hass)
    server_port = redirect_server.port

    # Redirect from an external origin to a relative path
    redirect_url = f"http://external.example.com:{server_port}/redirect?to=/ok"

    async def mock_async_resolve_host(host: str) -> list[dict[str, object]]:
        """Return public IPs for all hosts."""
        return _resolve_result(host, "93.184.216.34")

    connector = session.connector
    with patch.object(connector, "async_resolve_host", mock_async_resolve_host):
        resp = await session.get(redirect_url)
        assert resp.status == 200


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.parametrize(
    "target",
    [
        "http://other.example.com:{port}/ok",
        "http://safe.example.com:{port}/ok",
        "http://notlocalhost:{port}/ok",
    ],
)
async def test_redirect_to_non_loopback_allowed(
    hass: HomeAssistant, redirect_server: TestServer, target: str
) -> None:
    """Test that redirects to non-loopback addresses are allowed."""
    session = client.async_create_clientsession(hass)
    server_port = redirect_server.port

    location = target.format(port=server_port)
    redirect_url = f"http://external.example.com:{server_port}/redirect?to={location}"

    async def mock_async_resolve_host(host: str) -> list[dict[str, object]]:
        """Return public IPs for all hosts."""
        return _resolve_result(host, "93.184.216.34")

    connector = session.connector
    with patch.object(connector, "async_resolve_host", mock_async_resolve_host):
        resp = await session.get(redirect_url)
        assert resp.status == 200


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.parametrize(
    ("location", "target_resolved_addr"),
    [
        # Loopback IPs and hostnames — blocked before DNS resolution
        ("http://127.0.0.1/evil", None),
        ("http://[::1]/evil", None),
        ("http://localhost/evil", None),
        ("http://localhost./evil", None),
        ("http://example.localhost/evil", None),
        ("http://example.localhost./evil", None),
        ("http://app.localhost/evil", None),
        ("http://sub.domain.localhost/evil", None),
        # Benign hostnames resolving to blocked IPs — blocked after DNS
        ("http://evil.example.com:{port}/steal", "127.0.0.1"),
        ("http://evil.example.com:{port}/steal", "127.0.0.2"),
        ("http://evil.example.com:{port}/steal", "::1"),
        ("http://evil.example.com:{port}/steal", "0.0.0.0"),
        ("http://evil.example.com:{port}/steal", "::"),
    ],
)
async def test_redirect_to_blocked_address(
    hass: HomeAssistant,
    redirect_server: TestServer,
    location: str,
    target_resolved_addr: str | None,
) -> None:
    """Test that redirects to blocked addresses are blocked.

    Covers both cases: targets blocked by hostname/IP (before DNS) and
    targets blocked after DNS resolution reveals a loopback/unspecified IP.
    """
    session = client.async_create_clientsession(hass)
    server_port = redirect_server.port

    target = location.format(port=server_port)
    redirect_url = f"http://external.example.com:{server_port}/redirect?to={target}"

    async def mock_async_resolve_host(host: str) -> list[dict[str, object]]:
        """Return public IP for origin, optional blocked IP for target."""
        if host == "external.example.com":
            return _resolve_result(host, "93.184.216.34")
        if target_resolved_addr is not None:
            return _resolve_result(host, target_resolved_addr)
        return []

    connector = session.connector
    with (
        patch.object(connector, "async_resolve_host", mock_async_resolve_host),
        pytest.raises(client.SSRFRedirectError),
    ):
        await session.get(redirect_url)
