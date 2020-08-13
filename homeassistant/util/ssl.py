"""Helper to create SSL contexts."""
from os import environ
import ssl

import certifi


def client_context() -> ssl.SSLContext:
    """Return an SSL context for making requests."""

    # Reuse environment variable definition from requests, since it's already a requirement
    # If the environment variable has no value, fall back to using certs from certifi package
    cafile = environ.get("REQUESTS_CA_BUNDLE", certifi.where())

    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=cafile)
    return context


def server_context_modern() -> ssl.SSLContext:
    """Return an SSL context following the Mozilla recommendations.

    TLS configuration follows the best-practice guidelines specified here:
    https://wiki.mozilla.org/Security/Server_Side_TLS
    Modern guidelines are followed.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)  # pylint: disable=no-member

    context.options |= (
        ssl.OP_NO_SSLv2
        | ssl.OP_NO_SSLv3
        | ssl.OP_NO_TLSv1
        | ssl.OP_NO_TLSv1_1
        | ssl.OP_CIPHER_SERVER_PREFERENCE
    )
    if hasattr(ssl, "OP_NO_COMPRESSION"):
        context.options |= ssl.OP_NO_COMPRESSION

    context.set_ciphers(
        "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
        "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:"
        "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
        "ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA384:"
        "ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256"
    )

    return context


def server_context_intermediate() -> ssl.SSLContext:
    """Return an SSL context following the Mozilla recommendations.

    TLS configuration follows the best-practice guidelines specified here:
    https://wiki.mozilla.org/Security/Server_Side_TLS
    Intermediate guidelines are followed.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)  # pylint: disable=no-member

    context.options |= (
        ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_CIPHER_SERVER_PREFERENCE
    )
    if hasattr(ssl, "OP_NO_COMPRESSION"):
        context.options |= ssl.OP_NO_COMPRESSION

    context.set_ciphers(
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
    )

    return context
