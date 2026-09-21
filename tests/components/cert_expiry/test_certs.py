"""Real end-to-end tests for cert_expiry.certs, driven by checked-in cert fixtures."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import timedelta
import socket
import ssl
from unittest.mock import AsyncMock

from cryptography import x509
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.cert_expiry.certs import (
    HandshakePolicyVerifier,
    async_get_cert,
)
from homeassistant.components.cert_expiry.errors import (
    CertExpiryException,
    ConnectionFailed,
    ConnectionRefused,
    ConnectionReset,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)
from homeassistant.core import HomeAssistant

from .cert_helpers import (
    load_scenario,
    local_closed_port,
    local_garbage_server,
    local_reset_server,
    local_tls_server,
    local_unresponsive_server,
    server_context,
    trusted_context,
)


@pytest.mark.parametrize(
    "server",
    [
        ("rsa_leaf_with_full_chain", None),
        ("ec_leaf_with_full_chain", None),
        ("leaf_signed_directly_by_root", None),
        ("leaf_missing_intermediate", None),
        ("legacy_cipher_only_server", "AES256-GCM-SHA384"),
        pytest.param(
            ("rsa_leaf_with_full_chain", "DHE-RSA-CHACHA20-POLY1305"),
            id="cipher_outside_intermediate_list",
        ),
    ],
    ids=lambda server: server[0],
)
@pytest.mark.usefixtures("socket_enabled")
async def test_async_get_cert(
    hass: HomeAssistant, server: tuple[str, str | None]
) -> None:
    """The certificate is returned for each served certificate scenario."""
    scenario, ciphers = server
    cert = load_scenario(scenario)
    async with local_tls_server(server_context(cert, ciphers=ciphers)) as port:
        result = await async_get_cert(hass, "localhost", port)
    assert result.cert.not_valid_after_utc == cert.metadata.not_valid_after


@pytest.mark.usefixtures("socket_enabled")
async def test_async_get_cert_handshake_parameters(hass: HomeAssistant) -> None:
    """The negotiated TLS parameters are returned with the certificate."""
    cert = load_scenario("legacy_cipher_only_server")
    async with local_tls_server(
        server_context(cert, ciphers="AES256-GCM-SHA384")
    ) as port:
        result = await async_get_cert(hass, "localhost", port)
    assert result.tls_version == "TLSv1.2"
    assert result.cipher_name == "AES256-GCM-SHA384"
    assert result.cipher_protocol == "TLSv1.2"


@pytest.mark.parametrize(
    ("make_server", "exception"),
    [
        pytest.param(
            local_unresponsive_server, ConnectionTimeout, id="connection_timeout"
        ),
        pytest.param(local_closed_port, ConnectionRefused, id="connection_refused"),
        pytest.param(local_reset_server, ConnectionReset, id="connection_reset"),
        pytest.param(local_garbage_server, ValidationFailure, id="validation_failure"),
    ],
)
@pytest.mark.usefixtures("socket_enabled")
async def test_async_get_cert_errors(
    hass: HomeAssistant,
    make_server: Callable[[], AbstractAsyncContextManager[tuple[str, int]]],
    exception: type[CertExpiryException],
) -> None:
    """Each connection failure is translated into the matching domain error."""
    async with make_server() as (host, port):
        with pytest.raises(exception):
            await async_get_cert(hass, host, port, timeout=0.2)


@pytest.mark.usefixtures("socket_enabled")
async def test_async_get_cert_ssl_error_message(hass: HomeAssistant) -> None:
    """An SSL error's description is carried as the ValidationFailure message."""
    async with local_garbage_server() as (host, port):
        with pytest.raises(ValidationFailure, match=r"\[SSL: WRONG_VERSION_NUMBER\]"):
            await async_get_cert(hass, host, port, timeout=0.2)


async def test_async_get_cert_resolve_failed(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DNS resolution failure is translated into ResolveFailed.

    The test harness disables real DNS resolution for non-loopback hosts
    (see tests/conftest.py), so the failure is injected at hass.loop directly.
    """
    monkeypatch.setattr(
        hass.loop,
        "getaddrinfo",
        AsyncMock(side_effect=socket.gaierror("Name or service not known")),
    )
    with pytest.raises(ResolveFailed):
        await async_get_cert(hass, "cert-expiry-test.example", 443, timeout=0.2)


async def test_async_get_cert_connection_failed(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plain OSError from the connection is translated into ConnectionFailed."""
    monkeypatch.setattr(
        hass.loop,
        "getaddrinfo",
        AsyncMock(
            side_effect=OSError("Multiple exceptions: [Errno 111] Connect call failed")
        ),
    )
    with pytest.raises(ConnectionFailed):
        await async_get_cert(hass, "cert-expiry-test.example", 443, timeout=0.2)


@pytest.mark.parametrize(
    ("tls_version", "minimum_version", "maximum_version", "error"),
    [
        pytest.param(
            "TLSv1.2",
            ssl.TLSVersion.MINIMUM_SUPPORTED,
            ssl.TLSVersion.MAXIMUM_SUPPORTED,
            None,
            id="unbounded",
        ),
        pytest.param(
            "TLSv1.2",
            ssl.TLSVersion.TLSv1_2,
            ssl.TLSVersion.TLSv1_2,
            None,
            id="at_bounds",
        ),
        pytest.param(
            "TLSv1.2",
            ssl.TLSVersion.TLSv1_3,
            ssl.TLSVersion.MAXIMUM_SUPPORTED,
            "TLSv1.2 is below the minimum TLS version",
            id="below_minimum",
        ),
        pytest.param(
            "TLSv1.3",
            ssl.TLSVersion.MINIMUM_SUPPORTED,
            ssl.TLSVersion.TLSv1_2,
            "TLSv1.3 is above the maximum TLS version",
            id="above_maximum",
        ),
        pytest.param(
            None,
            ssl.TLSVersion.MINIMUM_SUPPORTED,
            ssl.TLSVersion.MAXIMUM_SUPPORTED,
            "No TLS version negotiated",
            id="no_version",
        ),
        pytest.param(
            "SSLv7",
            ssl.TLSVersion.MINIMUM_SUPPORTED,
            ssl.TLSVersion.MAXIMUM_SUPPORTED,
            "Unrecognized TLS version: SSLv7",
            id="unrecognized_version",
        ),
    ],
)
def test_verify_tls_version(
    tls_version: str | None,
    minimum_version: ssl.TLSVersion,
    maximum_version: ssl.TLSVersion,
    error: str | None,
) -> None:
    """The TLS version is checked against the allowed range."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = minimum_version
    context.maximum_version = maximum_version
    verifier = HandshakePolicyVerifier(context, "localhost")
    assert verifier.verify_tls_version(tls_version) == error


@pytest.mark.parametrize(
    ("cipher_name", "cipher_protocol", "error"),
    [
        pytest.param("ECDHE-RSA-AES256-GCM-SHA384", "TLSv1.2", None, id="allowed"),
        pytest.param(
            "AES256-GCM-SHA384",
            "TLSv1.2",
            "Cipher AES256-GCM-SHA384 is not enabled",
            id="not_enabled",
        ),
        pytest.param(
            "ECDHE-RSA-AES256-GCM-SHA384",
            "TLSv1.3",
            "Cipher ECDHE-RSA-AES256-GCM-SHA384 uses TLSv1.2, not TLSv1.3",
            id="protocol_mismatch",
        ),
        pytest.param(None, None, "Cipher None is not enabled", id="no_cipher"),
    ],
)
def test_verify_cipher(
    cipher_name: str | None,
    cipher_protocol: str | None,
    error: str | None,
) -> None:
    """The cipher is checked against the allowed cipher list."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.set_ciphers("ECDHE-RSA-AES256-GCM-SHA384")
    verifier = HandshakePolicyVerifier(context, "localhost")
    assert verifier.verify_cipher(cipher_name, cipher_protocol) == error


@pytest.mark.parametrize(
    ("scenario", "verified"),
    [
        pytest.param("rsa_leaf_with_full_chain", True, id="rsa_leaf_with_full_chain"),
        pytest.param("ec_leaf_with_full_chain", True, id="ec_leaf_with_full_chain"),
        pytest.param(
            "leaf_signed_directly_by_root", True, id="leaf_signed_directly_by_root"
        ),
        pytest.param(
            "leaf_missing_intermediate", False, id="leaf_missing_intermediate"
        ),
    ],
)
def test_verify_cert(scenario: str, verified: bool) -> None:
    """The certificate verifies only when a full chain to the trusted root exists.

    cert.pem holds the leaf plus whatever intermediates the scenario concatenates
    after it (see fixtures/generate.py), the same certificates a real handshake
    would present via get_unverified_chain().
    """
    cert = load_scenario(scenario)
    leaf, *intermediates = x509.load_pem_x509_certificates(cert.certfile.read_bytes())
    verifier = HandshakePolicyVerifier(trusted_context(), "localhost")
    error = verifier.verify_cert(leaf, intermediates)
    assert (error is None) == verified


@pytest.mark.usefixtures("socket_enabled")
async def test_async_get_cert_verify_cert_full_chain(hass: HomeAssistant) -> None:
    """verify_cert trusts a leaf whose intermediate arrived via the real handshake.

    Only the root CA is trusted; the intermediate must come from
    result.intermediates (captured from the server's TLS chain), not from the
    trust store, for this to verify.
    """
    cert = load_scenario("rsa_leaf_with_full_chain")
    async with local_tls_server(server_context(cert)) as port:
        result = await async_get_cert(hass, "localhost", port)
    verifier = HandshakePolicyVerifier(trusted_context(), "localhost")
    error = verifier.verify_cert(result.cert, result.intermediates)
    assert error is None


def test_verify_cert_uses_current_time_not_construction_time(
    freezer: FrozenDateTimeFactory,
) -> None:
    """verify_cert() must evaluate expiry against the current time on every call.

    ServerVerifier's validation_time is fixed at build_server_verifier() time,
    not at verify() time. If HandshakePolicyVerifier cached the built
    verifier instead of rebuilding it per call, a certificate that expired
    after construction would keep verifying as trusted for as long as the
    instance (and the coordinator that owns it) lived.
    """
    cert = load_scenario("rsa_leaf_with_full_chain")
    leaf, *intermediates = x509.load_pem_x509_certificates(cert.certfile.read_bytes())

    freezer.move_to(cert.metadata.not_valid_before)
    verifier = HandshakePolicyVerifier(trusted_context(), "localhost")
    assert verifier.verify_cert(leaf, intermediates) is None

    freezer.move_to(cert.metadata.not_valid_after + timedelta(seconds=1))
    assert verifier.verify_cert(leaf, intermediates) is not None
