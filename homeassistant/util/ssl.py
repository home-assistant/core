"""Helper to create SSL contexts."""
import contextlib
from functools import cache
from os import environ
import ssl

import certifi

from homeassistant.backports.enum import StrEnum


class SSLCipherList(StrEnum):
    """SSL cipher lists."""

    PYTHON_DEFAULT = "python_default"
    INTERMEDIATE = "intermediate"
    MODERN = "modern"


SSL_CIPHER_LISTS = {
    SSLCipherList.INTERMEDIATE: (
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
    SSLCipherList.MODERN: (
        "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
        "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:"
        "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
        "ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA384:"
        "ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256"
    ),
}


@cache
def create_no_verify_ssl_context(
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
) -> ssl.SSLContext:
    """Return an SSL context that does not verify the server certificate.

    This is a copy of aiohttp's create_default_context() function, with the
    ssl verify turned off.

    https://github.com/aio-libs/aiohttp/blob/33953f110e97eecc707e1402daa8d543f38a189b/aiohttp/connector.py#L911
    """
    sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    sslcontext.check_hostname = False
    sslcontext.verify_mode = ssl.CERT_NONE
    with contextlib.suppress(AttributeError):
        # This only works for OpenSSL >= 1.0.0
        sslcontext.options |= ssl.OP_NO_COMPRESSION
    sslcontext.set_default_verify_paths()
    if ssl_cipher_list != SSLCipherList.PYTHON_DEFAULT:
        sslcontext.set_ciphers(SSL_CIPHER_LISTS[ssl_cipher_list])

    return sslcontext


@cache
def client_context(
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
) -> ssl.SSLContext:
    """Return an SSL context for making requests."""

    # Reuse environment variable definition from requests, since it's already a
    # requirement. If the environment variable has no value, fall back to using
    # certs from certifi package.
    cafile = environ.get("REQUESTS_CA_BUNDLE", certifi.where())

    sslcontext = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH, cafile=cafile
    )
    if ssl_cipher_list != SSLCipherList.PYTHON_DEFAULT:
        sslcontext.set_ciphers(SSL_CIPHER_LISTS[ssl_cipher_list])

    return sslcontext


# Create this only once and reuse it
_DEFAULT_SSL_CONTEXT = client_context()
_DEFAULT_NO_VERIFY_SSL_CONTEXT = create_no_verify_ssl_context()


def get_default_context() -> ssl.SSLContext:
    """Return the default SSL context."""
    return _DEFAULT_SSL_CONTEXT


def get_default_no_verify_context() -> ssl.SSLContext:
    """Return the default SSL context that does not verify the server certificate."""
    return _DEFAULT_NO_VERIFY_SSL_CONTEXT


def server_context_modern() -> ssl.SSLContext:
    """Return an SSL context following the Mozilla recommendations.

    TLS configuration follows the best-practice guidelines specified here:
    https://wiki.mozilla.org/Security/Server_Side_TLS
    Modern guidelines are followed.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    context.options |= (
        ssl.OP_NO_SSLv2
        | ssl.OP_NO_SSLv3
        | ssl.OP_NO_TLSv1
        | ssl.OP_NO_TLSv1_1
        | ssl.OP_CIPHER_SERVER_PREFERENCE
    )
    if hasattr(ssl, "OP_NO_COMPRESSION"):
        context.options |= ssl.OP_NO_COMPRESSION

    context.set_ciphers(SSL_CIPHER_LISTS[SSLCipherList.MODERN])

    return context


def server_context_intermediate() -> ssl.SSLContext:
    """Return an SSL context following the Mozilla recommendations.

    TLS configuration follows the best-practice guidelines specified here:
    https://wiki.mozilla.org/Security/Server_Side_TLS
    Intermediate guidelines are followed.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    context.options |= (
        ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_CIPHER_SERVER_PREFERENCE
    )
    if hasattr(ssl, "OP_NO_COMPRESSION"):
        context.options |= ssl.OP_NO_COMPRESSION

    context.set_ciphers(SSL_CIPHER_LISTS[SSLCipherList.INTERMEDIATE])

    return context
