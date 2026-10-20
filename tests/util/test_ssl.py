"""Test Home Assistant ssl utility functions."""

from datetime import timedelta
from pathlib import Path
import ssl

import certifi
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import pytest

from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import (
    SSL_ALPN_HTTP11,
    SSL_ALPN_HTTP11_HTTP2,
    SSL_ALPN_NONE,
    SSL_CIPHER_LISTS,
    SSLCipherList,
    SSLProfile,
    client_context,
    client_context_no_verify,
    create_client_context,
    create_no_verify_ssl_context,
    get_default_context,
    get_default_no_verify_context,
    server_context,
)

# Required by every profile; the TLS 1.3 suites come from the OpenSSL
# defaults, which the system config may extend with other AEAD suites.
_TLS13_CIPHERS = {
    "TLS_AES_128_GCM_SHA256",
    "TLS_AES_256_GCM_SHA384",
    "TLS_CHACHA20_POLY1305_SHA256",
}


def _tls13_ciphers(context: ssl.SSLContext) -> set[str]:
    return {c["name"] for c in context.get_ciphers() if c["protocol"] == "TLSv1.3"}


def _legacy_ciphers(context: ssl.SSLContext) -> list[str]:
    """Return the ciphers below TLS 1.3, the ones set_ciphers() controls."""
    return [c["name"] for c in context.get_ciphers() if c["protocol"] != "TLSv1.3"]


def test_ssl_context_caching() -> None:
    """Test that SSLContext instances are cached correctly."""
    assert client_context() is client_context(SSLCipherList.PYTHON_DEFAULT)
    assert create_no_verify_ssl_context() is create_no_verify_ssl_context(
        SSLCipherList.PYTHON_DEFAULT
    )


def test_ssl_context_cipher_bucketing() -> None:
    """Test that SSL contexts are bucketed by cipher list."""
    default_ctx = client_context(SSLCipherList.PYTHON_DEFAULT)
    modern_ctx = client_context(SSLCipherList.MODERN)
    intermediate_ctx = client_context(SSLCipherList.INTERMEDIATE)
    insecure_ctx = client_context(SSLCipherList.INSECURE)

    # Different cipher lists should return different contexts
    assert default_ctx is not modern_ctx
    assert default_ctx is not intermediate_ctx
    assert default_ctx is not insecure_ctx
    assert modern_ctx is not intermediate_ctx
    assert modern_ctx is not insecure_ctx
    assert intermediate_ctx is not insecure_ctx

    # Same parameters should return cached context
    assert client_context(SSLCipherList.PYTHON_DEFAULT) is default_ctx
    assert client_context(SSLCipherList.MODERN) is modern_ctx


def test_no_verify_ssl_context_cipher_bucketing() -> None:
    """Test that no-verify SSL contexts are bucketed by cipher list."""
    default_ctx = create_no_verify_ssl_context(SSLCipherList.PYTHON_DEFAULT)
    modern_ctx = create_no_verify_ssl_context(SSLCipherList.MODERN)

    # Different cipher lists should return different contexts
    assert default_ctx is not modern_ctx

    # Same parameters should return cached context
    assert create_no_verify_ssl_context(SSLCipherList.PYTHON_DEFAULT) is default_ctx
    assert create_no_verify_ssl_context(SSLCipherList.MODERN) is modern_ctx


def test_create_client_context_independent() -> None:
    """Test create_client_context independence."""
    shared_context = client_context()
    independent_context_1 = create_client_context()
    independent_context_2 = create_client_context()
    assert shared_context is not independent_context_1
    assert independent_context_1 is not independent_context_2


def test_ssl_context_alpn_bucketing() -> None:
    """Test that SSL contexts are bucketed by ALPN protocols.

    Different ALPN protocol configurations should return different cached contexts
    to prevent downstream libraries (e.g., httpx/httpcore) from mutating shared
    contexts with incompatible settings.
    """
    # HTTP/1.1, HTTP/2, and no-ALPN contexts should all be different
    http1_context = client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11)
    http2_context = client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11_HTTP2)
    no_alpn_context = client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_NONE)
    assert http1_context is not http2_context
    assert http1_context is not no_alpn_context
    assert http2_context is not no_alpn_context

    # Same parameters should return cached context
    assert (
        client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11) is http1_context
    )
    assert (
        client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11_HTTP2)
        is http2_context
    )
    assert (
        client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_NONE) is no_alpn_context
    )

    # No-verify contexts should also be bucketed by ALPN
    http1_no_verify = client_context_no_verify(
        SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11
    )
    http2_no_verify = client_context_no_verify(
        SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11_HTTP2
    )
    no_alpn_no_verify = client_context_no_verify(
        SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_NONE
    )
    assert http1_no_verify is not http2_no_verify
    assert http1_no_verify is not no_alpn_no_verify
    assert http2_no_verify is not no_alpn_no_verify

    # create_no_verify_ssl_context should also work with ALPN
    assert (
        create_no_verify_ssl_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11)
        is http1_no_verify
    )
    assert (
        create_no_verify_ssl_context(
            SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11_HTTP2
        )
        is http2_no_verify
    )
    assert (
        create_no_verify_ssl_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_NONE)
        is no_alpn_no_verify
    )


def test_ssl_context_insecure_alpn_bucketing() -> None:
    """Test that INSECURE cipher list SSL contexts are bucketed by ALPN protocols.

    INSECURE cipher list is used by some integrations that need to connect to
    devices with outdated TLS implementations.
    """
    # HTTP/1.1, HTTP/2, and no-ALPN contexts should all be different
    http1_context = client_context(SSLCipherList.INSECURE, SSL_ALPN_HTTP11)
    http2_context = client_context(SSLCipherList.INSECURE, SSL_ALPN_HTTP11_HTTP2)
    no_alpn_context = client_context(SSLCipherList.INSECURE, SSL_ALPN_NONE)
    assert http1_context is not http2_context
    assert http1_context is not no_alpn_context
    assert http2_context is not no_alpn_context

    # Same parameters should return cached context
    assert client_context(SSLCipherList.INSECURE, SSL_ALPN_HTTP11) is http1_context
    assert (
        client_context(SSLCipherList.INSECURE, SSL_ALPN_HTTP11_HTTP2) is http2_context
    )
    assert client_context(SSLCipherList.INSECURE, SSL_ALPN_NONE) is no_alpn_context

    # No-verify contexts should also be bucketed by ALPN
    http1_no_verify = client_context_no_verify(SSLCipherList.INSECURE, SSL_ALPN_HTTP11)
    http2_no_verify = client_context_no_verify(
        SSLCipherList.INSECURE, SSL_ALPN_HTTP11_HTTP2
    )
    no_alpn_no_verify = client_context_no_verify(SSLCipherList.INSECURE, SSL_ALPN_NONE)
    assert http1_no_verify is not http2_no_verify
    assert http1_no_verify is not no_alpn_no_verify
    assert http2_no_verify is not no_alpn_no_verify

    # create_no_verify_ssl_context should also work with ALPN
    assert (
        create_no_verify_ssl_context(SSLCipherList.INSECURE, SSL_ALPN_HTTP11)
        is http1_no_verify
    )
    assert (
        create_no_verify_ssl_context(SSLCipherList.INSECURE, SSL_ALPN_HTTP11_HTTP2)
        is http2_no_verify
    )
    assert (
        create_no_verify_ssl_context(SSLCipherList.INSECURE, SSL_ALPN_NONE)
        is no_alpn_no_verify
    )


def test_get_default_context_uses_http1_alpn() -> None:
    """Test that get_default_context returns context with HTTP1 ALPN."""
    default_ctx = get_default_context()
    default_no_verify_ctx = get_default_no_verify_context()

    # Default contexts should be the same as explicitly requesting HTTP1 ALPN
    assert default_ctx is client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11)
    assert default_no_verify_ctx is client_context_no_verify(
        SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11
    )


def test_client_context_default_no_alpn() -> None:
    """Test that client_context defaults to no ALPN for backward compatibility."""
    # Default (no ALPN) should be different from HTTP1 ALPN
    default_ctx = client_context()
    http1_ctx = client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11)

    assert default_ctx is not http1_ctx
    assert default_ctx is client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_NONE)


def test_server_context_modern_v6() -> None:
    """The v6.0 modern profile is TLS 1.3 only and lets the client pick the cipher."""
    context = server_context(SSLProfile.MODERN_V6)
    assert context.minimum_version == ssl.TLSVersion.TLSv1_3
    assert context.options & ssl.OP_NO_COMPRESSION
    assert not context.options & ssl.OP_CIPHER_SERVER_PREFERENCE
    assert _tls13_ciphers(context) >= _TLS13_CIPHERS


def test_server_context_intermediate_v6() -> None:
    """The v6.0 intermediate profile allows TLS 1.2 with its AEAD ECDHE suites."""
    context = server_context(SSLProfile.INTERMEDIATE_V6)
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2
    assert context.options & ssl.OP_NO_COMPRESSION
    assert not context.options & ssl.OP_CIPHER_SERVER_PREFERENCE
    assert _tls13_ciphers(context) >= _TLS13_CIPHERS

    expected = [
        "ECDHE-ECDSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-CHACHA20-POLY1305",
        "ECDHE-RSA-CHACHA20-POLY1305",
    ]
    # The system OpenSSL policy may disable some of the suites, never add any.
    ciphers = _legacy_ciphers(context)
    assert ciphers
    assert ciphers == [cipher for cipher in expected if cipher in ciphers]


def test_server_context_v4_profiles() -> None:
    """The v4 profiles keep the settings existing installs connect with."""
    modern = server_context(SSLProfile.MODERN_V4)
    assert modern.minimum_version == ssl.TLSVersion.TLSv1_2
    assert modern.options & ssl.OP_NO_COMPRESSION
    assert modern.options & ssl.OP_CIPHER_SERVER_PREFERENCE
    assert _tls13_ciphers(modern) >= _TLS13_CIPHERS
    assert set(_legacy_ciphers(modern)) <= set(
        SSL_CIPHER_LISTS[SSLProfile.MODERN_V4].split(":")
    )

    intermediate = server_context(SSLProfile.INTERMEDIATE_V4)
    assert intermediate.minimum_version == ssl.TLSVersion.TLSv1_2
    assert intermediate.options & ssl.OP_NO_COMPRESSION
    assert intermediate.options & ssl.OP_CIPHER_SERVER_PREFERENCE
    assert _tls13_ciphers(intermediate) >= _TLS13_CIPHERS
    assert set(_legacy_ciphers(intermediate)) <= set(
        SSL_CIPHER_LISTS[SSLProfile.INTERMEDIATE_V4].split(":")
    )


def test_create_client_context_uses_certifi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test client contexts trust the certifi CA certificates by default."""
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    expected = ssl.create_default_context(cafile=certifi.where())

    context = create_client_context()

    assert context.cert_store_stats() == expected.cert_store_stats()


def test_create_client_context_uses_requests_ca_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test client contexts trust REQUESTS_CA_BUNDLE when set."""
    certifi_bundle = Path(certifi.where()).read_text(encoding="utf-8")
    end_marker = "-----END CERTIFICATE-----"
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text(
        certifi_bundle[: certifi_bundle.index(end_marker)] + end_marker,
        encoding="utf-8",
    )
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(ca_bundle))

    context = create_client_context()

    assert context.cert_store_stats()["x509_ca"] == 1


def test_create_client_context_keeps_non_ca_certs_in_requests_ca_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test explicitly trusted non-CA certificates in REQUESTS_CA_BUNDLE are kept."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = dt_util.utcnow()
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    ca_bundle = tmp_path / "server.pem"
    ca_bundle.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(ca_bundle))

    context = create_client_context()

    assert context.cert_store_stats() == {"x509": 1, "crl": 0, "x509_ca": 0}
