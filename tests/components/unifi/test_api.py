"""Test UniFi TLS validation using real loopback HTTPS and WebSocket connections."""

import asyncio
from collections.abc import AsyncGenerator, Callable
from datetime import timedelta
from ipaddress import ip_address
from pathlib import Path
import ssl
from typing import Any
from unittest.mock import Mock, patch

from aiohttp import ClientConnectorCertificateError, web
from aiohttp.test_utils import TestServer
import aiounifi
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import pytest

from homeassistant.components.unifi.const import CONF_SITE_ID
from homeassistant.components.unifi.errors import CannotConnect
from homeassistant.components.unifi.hub.api import get_unifi_api
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


@pytest.fixture(autouse=True)
def mock_websocket_state() -> None:
    """Allow real HTTP rather than the integration's default request mock."""


@pytest.fixture(autouse=True)
def _mock_websocket() -> None:
    """Allow the real aiounifi WebSocket implementation."""


@pytest.fixture
def tls_contexts(
    tmp_path: Path, certificate_matches: bool, trusted: bool
) -> tuple[ssl.SSLContext, ssl.SSLContext, Path]:
    """Create an ephemeral server certificate and independent client trust store."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "UniFi test")])
    identity = "127.0.0.1" if certificate_matches else "127.0.0.2"
    now = dt_util.utcnow()
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ip_address(identity))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "server.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path = tmp_path / "server.key"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert_path, key_path)
    client_context = ssl.create_default_context()
    if trusted:
        client_context.load_verify_locations(cafile=cert_path)
    return server_context, client_context, cert_path


@pytest.fixture
async def tls_controller(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    tls_contexts: tuple[ssl.SSLContext, ssl.SSLContext, Path],
    verify_ssl: bool | str | None,
    socket_enabled: None,
) -> AsyncGenerator[tuple[dict[str, Any], list[str]]]:
    """Serve a minimal UniFi controller over loopback TLS."""
    server_context, client_context, cert_path = tls_contexts
    requests: list[str] = []

    async def handle(request: web.Request) -> web.StreamResponse:
        requests.append(request.path)
        if request.path.startswith("/wss/"):
            websocket = web.WebSocketResponse()
            await websocket.prepare(request)
            await websocket.send_str("tls-verified")
            await websocket.close()
            return websocket
        return web.json_response(
            {"meta": {"rc": "ok"}, "data": []},
            status=200 if request.method == "POST" else 302,
        )

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handle)
    server = await aiohttp_server(app, ssl=server_context)
    config = {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: server.port,
        CONF_USERNAME: "test-user",
        CONF_PASSWORD: "test-password",
        CONF_SITE_ID: "default",
    }
    if verify_ssl is not None:
        config[CONF_VERIFY_SSL] = (
            str(cert_path) if verify_ssl == "ca-file" else verify_ssl
        )

    loop = asyncio.get_running_loop()
    original_handler = loop.get_exception_handler()

    def exception_handler(
        loop: asyncio.AbstractEventLoop, context: dict[str, Any]
    ) -> None:
        # A client rejecting the certificate can reset the server's TLS handshake.
        if context.get(
            "message"
        ) == "Error on transport creation for incoming connection" and isinstance(
            context.get("exception"), ConnectionResetError
        ):
            return
        assert original_handler is not None
        original_handler(loop, context)

    loop.set_exception_handler(exception_handler)
    # Substitute only the default trust store, never the transport or TLS options.
    with patch(
        "homeassistant.util.ssl.get_default_context", return_value=client_context
    ):
        try:
            yield config, requests
        finally:
            await hass.async_block_till_done()
            loop.set_exception_handler(original_handler)


@pytest.fixture
async def websocket_api(
    hass: HomeAssistant, tls_controller: tuple[dict[str, Any], list[str]]
) -> aiounifi.Controller:
    """Skip login so HTTPS rejection cannot mask a WebSocket validation defect."""
    config, _ = tls_controller
    with patch("aiounifi.Controller.login"):
        return await get_unifi_api(hass, config)


ACCEPTED_CERTIFICATES = pytest.mark.parametrize(
    ("verify_ssl", "trusted", "certificate_matches"),
    [
        pytest.param(True, True, True, id="verify-trusted"),
        pytest.param(False, False, True, id="disabled-untrusted"),
        pytest.param(False, False, False, id="disabled-wrong-host"),
        pytest.param(None, False, True, id="omitted"),
        pytest.param("ca-file", False, True, id="custom-ca"),
    ],
)
REJECTED_CERTIFICATES = pytest.mark.parametrize(
    ("verify_ssl", "trusted", "certificate_matches"),
    [
        pytest.param(True, False, True, id="verify-untrusted"),
        pytest.param(True, True, False, id="verify-wrong-host"),
        pytest.param("ca-file", False, False, id="custom-ca-wrong-host"),
    ],
)


@ACCEPTED_CERTIFICATES
async def test_https_accepts_certificate(
    hass: HomeAssistant, tls_controller: tuple[dict[str, Any], list[str]]
) -> None:
    """Verify login succeeds with the configured certificate policy."""
    config, requests = tls_controller
    await get_unifi_api(hass, config)
    assert requests == ["/", "/api/login"]


@REJECTED_CERTIFICATES
async def test_https_rejects_certificate(
    hass: HomeAssistant, tls_controller: tuple[dict[str, Any], list[str]]
) -> None:
    """Reject invalid certificates before sending any HTTP request."""
    config, requests = tls_controller
    with pytest.raises(CannotConnect) as exc:
        await get_unifi_api(hass, config)
    assert "certificate verify failed" in str(exc.value.__cause__)
    assert requests == []


@ACCEPTED_CERTIFICATES
async def test_websocket_accepts_certificate(
    websocket_api: aiounifi.Controller,
    tls_controller: tuple[dict[str, Any], list[str]],
) -> None:
    """Verify the real WebSocket handshake and delivery of a message."""
    _, requests = tls_controller
    message = Mock()
    await websocket_api.connectivity.websocket(message)
    message.assert_called_once_with("tls-verified")
    assert requests == ["/wss/s/default/events"]


@REJECTED_CERTIFICATES
async def test_websocket_rejects_certificate(
    websocket_api: aiounifi.Controller,
    tls_controller: tuple[dict[str, Any], list[str]],
) -> None:
    """Reject invalid certificates before the WebSocket upgrade."""
    _, requests = tls_controller
    message = Mock()
    with pytest.raises(ClientConnectorCertificateError):
        await websocket_api.connectivity.websocket(message)
    message.assert_not_called()
    assert requests == []
