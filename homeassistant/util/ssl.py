"""Helper to create SSL contexts."""

import contextlib
from enum import StrEnum
from functools import cache
from os import environ
import ssl

import certifi

# Type alias for ALPN protocols tuple (None means no ALPN protocols set)
type SSLALPNProtocols = tuple[str, ...] | None

# ALPN protocol configurations
# No ALPN protocols - used for libraries that don't support/need ALPN (e.g., aioimap)
SSL_ALPN_NONE: SSLALPNProtocols = None
# HTTP/1.1 only - used by default and for aiohttp (which doesn't support HTTP/2)
SSL_ALPN_HTTP11: SSLALPNProtocols = ("http/1.1",)
# HTTP/1.1 with HTTP/2 support - used when httpx http2=True
SSL_ALPN_HTTP11_HTTP2: SSLALPNProtocols = ("http/1.1", "h2")


class SSLCipherList(StrEnum):
    """Cipher list options for client connections."""

    PYTHON_DEFAULT = "python_default"
    INTERMEDIATE = "intermediate"
    MODERN = "modern"
    INSECURE = "insecure"


class SSLProfile(StrEnum):
    """Mozilla server side TLS profiles, named after the guideline version.

    https://docs.tlsref.org/server-side-tls.html (formerly
    https://wiki.mozilla.org/Security/Server_Side_TLS)

    A profile never changes once released: clients connect with it, so a
    newer guideline is a new profile and the user opts in to the upgrade.

    A profile covers the protocol versions and cipher suites. The certificate
    type and key size the guidelines also recommend come from the configured
    certificate and are not enforced.
    """

    MODERN_V4 = "modern_v4"
    INTERMEDIATE_V4 = "intermediate_v4"
    MODERN_V6 = "modern_v6"
    INTERMEDIATE_V6 = "intermediate_v6"


# Cipher suites below TLS 1.3 of each profile. TLS 1.3 suites cannot be
# configured through Python's ssl module; OpenSSL's defaults are the three
# suites the profiles require (the system OpenSSL config may add other AEAD
# TLS 1.3 suites). The v6.0 modern profile is TLS 1.3 only and has no entry.
SSL_CIPHER_LISTS = {
    SSLProfile.INTERMEDIATE_V4: (
        "ECDHE-ECDSA-CHACHA20-POLY1305:"
        "ECDHE-RSA-CHACHA20-POLY1305:"
        "ECDHE-ECDSA-AES128-GCM-SHA256:"
        "ECDHE-RSA-AES128-GCM-SHA256:"
        "ECDHE-ECDSA-AES256-GCM-SHA384:"
        "ECDHE-RSA-AES256-GCM-SHA384:"
        "DHE-RSA-AES128-GCM-SHA256:"
        "DHE-RSA-AES256-GCM-SHA384:"
        "ECDHE-ECDSA-AES128-SHA256:"
        "ECDHE-RSA-AES128-SHA256:"
        "ECDHE-ECDSA-AES128-SHA:"
        "ECDHE-RSA-AES256-SHA384:"
        "ECDHE-RSA-AES128-SHA:"
        "ECDHE-ECDSA-AES256-SHA384:"
        "ECDHE-ECDSA-AES256-SHA:"
        "ECDHE-RSA-AES256-SHA:"
        "DHE-RSA-AES128-SHA256:"
        "DHE-RSA-AES128-SHA:"
        "DHE-RSA-AES256-SHA256:"
        "DHE-RSA-AES256-SHA:"
        "ECDHE-ECDSA-DES-CBC3-SHA:"
        "ECDHE-RSA-DES-CBC3-SHA:"
        "EDH-RSA-DES-CBC3-SHA:"
        "AES128-GCM-SHA256:"
        "AES256-GCM-SHA384:"
        "AES128-SHA256:"
        "AES256-SHA256:"
        "AES128-SHA:"
        "AES256-SHA:"
        "DES-CBC3-SHA:"
        "!DSS"
    ),
    SSLProfile.MODERN_V4: (
        "ECDHE-ECDSA-AES256-GCM-SHA384:"
        "ECDHE-RSA-AES256-GCM-SHA384:"
        "ECDHE-ECDSA-CHACHA20-POLY1305:"
        "ECDHE-RSA-CHACHA20-POLY1305:"
        "ECDHE-ECDSA-AES128-GCM-SHA256:"
        "ECDHE-RSA-AES128-GCM-SHA256:"
        "ECDHE-ECDSA-AES256-SHA384:"
        "ECDHE-RSA-AES256-SHA384:"
        "ECDHE-ECDSA-AES128-SHA256:"
        "ECDHE-RSA-AES128-SHA256"
    ),
    SSLProfile.INTERMEDIATE_V6: (
        "ECDHE-ECDSA-AES128-GCM-SHA256:"
        "ECDHE-RSA-AES128-GCM-SHA256:"
        "ECDHE-ECDSA-AES256-GCM-SHA384:"
        "ECDHE-RSA-AES256-GCM-SHA384:"
        "ECDHE-ECDSA-CHACHA20-POLY1305:"
        "ECDHE-RSA-CHACHA20-POLY1305"
    ),
}

# The client cipher list options predate the versioned profiles and name the
# v4 ones. Changing them changes outgoing connections (e.g. rest, scrape, imap).
_CLIENT_CIPHER_LISTS = {
    SSLCipherList.INTERMEDIATE: SSL_CIPHER_LISTS[SSLProfile.INTERMEDIATE_V4],
    SSLCipherList.MODERN: SSL_CIPHER_LISTS[SSLProfile.MODERN_V4],
    SSLCipherList.INSECURE: "DEFAULT:@SECLEVEL=0",
}


@cache
def _client_context_no_verify(
    ssl_cipher_list: SSLCipherList,
    alpn_protocols: SSLALPNProtocols,
) -> ssl.SSLContext:
    # This is a copy of aiohttp's create_default_context() function, with the
    # ssl verify turned off.
    # https://github.com/aio-libs/aiohttp/blob/33953f110e97eecc707e1402daa8d543f38a189b/aiohttp/connector.py#L911

    sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    sslcontext.check_hostname = False
    sslcontext.verify_mode = ssl.CERT_NONE
    with contextlib.suppress(AttributeError):
        # This only works for OpenSSL >= 1.0.0
        sslcontext.options |= ssl.OP_NO_COMPRESSION
    sslcontext.set_default_verify_paths()
    if ssl_cipher_list != SSLCipherList.PYTHON_DEFAULT:
        sslcontext.set_ciphers(_CLIENT_CIPHER_LISTS[ssl_cipher_list])
    # Set ALPN protocols to prevent downstream libraries (e.g., httpx/httpcore)
    # from mutating the shared SSL context with different protocol settings.
    # If alpn_protocols is None, don't set ALPN (for libraries like aioimap).
    if alpn_protocols is not None:
        sslcontext.set_alpn_protocols(list(alpn_protocols))

    return sslcontext


def _create_client_context(
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
    alpn_protocols: SSLALPNProtocols = SSL_ALPN_NONE,
) -> ssl.SSLContext:
    """Return an independent SSL context for making requests."""
    # Reuse environment variable definition from requests, since it's already a
    # requirement. If the environment variable has no value, fall back to using
    # certs from certifi package.
    cafile = environ.get("REQUESTS_CA_BUNDLE", certifi.where())

    sslcontext = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH, cafile=cafile
    )
    if ssl_cipher_list != SSLCipherList.PYTHON_DEFAULT:
        sslcontext.set_ciphers(_CLIENT_CIPHER_LISTS[ssl_cipher_list])
    # Set ALPN protocols to prevent downstream libraries (e.g., httpx/httpcore)
    # from mutating the shared SSL context with different protocol settings.
    # If alpn_protocols is None, don't set ALPN (for libraries like aioimap).
    if alpn_protocols is not None:
        sslcontext.set_alpn_protocols(list(alpn_protocols))

    return sslcontext


@cache
def _client_context(
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
    alpn_protocols: SSLALPNProtocols = SSL_ALPN_NONE,
) -> ssl.SSLContext:
    # Cached version of _create_client_context
    return _create_client_context(ssl_cipher_list, alpn_protocols)


# Pre-warm the cache for ALL SSL context configurations at module load time.
# This is critical because creating SSL contexts loads certificates from disk,
# which is blocking I/O that must not happen in the event loop.
_SSL_ALPN_PROTOCOLS = (SSL_ALPN_NONE, SSL_ALPN_HTTP11, SSL_ALPN_HTTP11_HTTP2)
for _cipher in SSLCipherList:
    for _alpn in _SSL_ALPN_PROTOCOLS:
        _client_context(_cipher, _alpn)
        _client_context_no_verify(_cipher, _alpn)


def get_default_context() -> ssl.SSLContext:
    """Return the default SSL context."""
    return _client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11)


def get_default_no_verify_context() -> ssl.SSLContext:
    """Return the default SSL context that does not verify the server certificate."""
    return _client_context_no_verify(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11)


def client_context_no_verify(
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
    alpn_protocols: SSLALPNProtocols = SSL_ALPN_NONE,
) -> ssl.SSLContext:
    """Return a SSL context with no verification with a specific ssl cipher."""
    return _client_context_no_verify(ssl_cipher_list, alpn_protocols)


def client_context(
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
    alpn_protocols: SSLALPNProtocols = SSL_ALPN_NONE,
) -> ssl.SSLContext:
    """Return an SSL context for making requests."""
    return _client_context(ssl_cipher_list, alpn_protocols)


def create_client_context(
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
    alpn_protocols: SSLALPNProtocols = SSL_ALPN_NONE,
) -> ssl.SSLContext:
    """Return an independent SSL context for making requests."""
    # This explicitly uses the non-cached version to create a client context
    return _create_client_context(ssl_cipher_list, alpn_protocols)


def create_no_verify_ssl_context(
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
    alpn_protocols: SSLALPNProtocols = SSL_ALPN_NONE,
) -> ssl.SSLContext:
    """Return an SSL context that does not verify the server certificate."""
    return _client_context_no_verify(ssl_cipher_list, alpn_protocols)


def server_context(profile: SSLProfile) -> ssl.SSLContext:
    """Return a server SSL context following the given Mozilla profile."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    if hasattr(ssl, "OP_NO_COMPRESSION"):
        context.options |= ssl.OP_NO_COMPRESSION

    match profile:
        case SSLProfile.MODERN_V6:
            # TLS 1.3 only. The v6.0 profiles let the client choose the cipher,
            # which Python's server contexts do not by default.
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            context.options &= ~ssl.OP_CIPHER_SERVER_PREFERENCE
        case SSLProfile.INTERMEDIATE_V6:
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.options &= ~ssl.OP_CIPHER_SERVER_PREFERENCE
        case SSLProfile.MODERN_V4 | SSLProfile.INTERMEDIATE_V4:
            # The v4 profiles differ only in their cipher lists. Intermediate
            # previously inherited this floor from Python's default context.
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.options |= ssl.OP_CIPHER_SERVER_PREFERENCE

    if (ciphers := SSL_CIPHER_LISTS.get(profile)) is not None:
        context.set_ciphers(ciphers)

    return context
