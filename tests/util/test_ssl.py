"""Test Home Assistant ssl utility functions."""

import ssl

from homeassistant.util.ssl import (
    SSL_ALPN_HTTP11,
    SSL_ALPN_HTTP11_HTTP2,
    SSL_ALPN_NONE,
    SSLCipherList,
    client_context,
    client_context_no_verify,
    create_client_context,
    create_no_verify_ssl_context,
    get_default_context,
    get_default_no_verify_context,
    server_context_intermediate,
    server_context_modern,
)


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


def test_server_context_modern() -> None:
    """Modern server profile should only allow TLS 1.3 per Mozilla guidelines."""
    context = server_context_modern()
    assert context.minimum_version == ssl.TLSVersion.TLSv1_3

    tls13_ciphers = [
        cipher["name"]
        for cipher in context.get_ciphers()
        if cipher["protocol"] == "TLSv1.3"
    ]
    # Exact equality is not portable: system OpenSSL config (e.g. Fedora/RHEL
    # crypto-policies) may add other AEAD TLS 1.3 suites such as CCM.
    assert {
        "TLS_AES_128_GCM_SHA256",
        "TLS_AES_256_GCM_SHA384",
        "TLS_CHACHA20_POLY1305_SHA256",
    } <= set(tls13_ciphers)


def test_server_context_intermediate() -> None:
    """Intermediate server profile should follow the Mozilla guidelines."""
    context = server_context_intermediate()
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2

    tls13_ciphers = [
        cipher["name"]
        for cipher in context.get_ciphers()
        if cipher["protocol"] == "TLSv1.3"
    ]
    # Same as modern: TLS 1.3 suites come from OpenSSL defaults / system config.
    assert {
        "TLS_AES_128_GCM_SHA256",
        "TLS_AES_256_GCM_SHA384",
        "TLS_CHACHA20_POLY1305_SHA256",
    } <= set(tls13_ciphers)

    # set_ciphers() selects this ordered Mozilla intermediate list. System
    # OpenSSL policy may disable some of the suites, so require: non-empty,
    # no unexpected names, and preserved relative order among those present.
    expected_tls12 = [
        "ECDHE-ECDSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-CHACHA20-POLY1305",
        "ECDHE-RSA-CHACHA20-POLY1305",
    ]
    tls12_ciphers = [
        cipher["name"]
        for cipher in context.get_ciphers()
        if cipher["protocol"] == "TLSv1.2"
    ]
    assert tls12_ciphers
    assert set(tls12_ciphers) <= set(expected_tls12)
    assert tls12_ciphers == [c for c in expected_tls12 if c in tls12_ciphers]
