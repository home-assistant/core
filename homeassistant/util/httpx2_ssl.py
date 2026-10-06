"""Certifi-backed default SSL context for httpx2.

httpx2 and httpcore2 build their default SSL contexts with truststore. On Linux,
truststore reloads the system CA store on every TLS handshake, which blocks the
event loop. This replaces truststore's SSLContext with one verified against
certifi, matching httpx and the rest of Home Assistant.

The certifi CA data is shared with homeassistant.util.ssl. Unlike that module,
REQUESTS_CA_BUNDLE is not honored here, matching httpx: it only applies to the
SSL contexts Home Assistant creates for its own HTTP client helpers.
"""

from os import environ
import ssl
import sys
from typing import Self

import truststore

from .ca_certs import certifi_ca_data

# Load once at import, so creating a context in the event loop does not read
# the CA bundle from disk.
certifi_ca_data()


class CertifiSSLContext(ssl.SSLContext):
    """Client SSL context verified against certifi, as httpx used to create."""

    def __new__(cls, protocol: int = ssl.PROTOCOL_TLS_CLIENT) -> Self:
        """Default to a client context, like truststore."""
        return super().__new__(cls, protocol)

    def __init__(self, protocol: int = ssl.PROTOCOL_TLS_CLIENT) -> None:
        """Load the certifi CA certificates."""
        super().__init__()
        self.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN | ssl.VERIFY_X509_STRICT
        self.load_verify_locations(cadata=certifi_ca_data())
        # Match ssl.create_default_context(), which httpx used
        if (keylogfile := environ.get("SSLKEYLOGFILE")) and not (
            sys.flags.ignore_environment
        ):
            self.keylog_filename = keylogfile


def setup_certifi_ssl_context() -> None:
    """Replace truststore.SSLContext with the certifi-backed context."""
    truststore.SSLContext = CertifiSSLContext  # type: ignore[misc,assignment]
