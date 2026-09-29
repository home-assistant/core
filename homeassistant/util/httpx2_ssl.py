"""Certifi-backed default SSL context for httpx2.

httpx2 and httpcore2 build their default SSL contexts with truststore. On Linux,
truststore reloads the system CA store on every TLS handshake, which blocks the
event loop. This replaces truststore's SSLContext with one verified against
certifi, matching httpx and the rest of Home Assistant.
"""

from os import environ
import ssl
import sys
from typing import Self

import certifi
import truststore


def _load_certifi_ca_data() -> bytes:
    """Return the certifi CA certificates in DER form."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=certifi.where())
    return b"".join(context.get_ca_certs(binary_form=True))


# Load once at import, so creating a context in the event loop does not read
# the CA bundle from disk.
_CERTIFI_CA_DATA = _load_certifi_ca_data()


class CertifiSSLContext(ssl.SSLContext):
    """Client SSL context verified against certifi, as httpx used to create."""

    def __new__(cls, protocol: int = ssl.PROTOCOL_TLS_CLIENT) -> Self:
        """Default to a client context, like truststore."""
        return super().__new__(cls, protocol)

    def __init__(self, protocol: int = ssl.PROTOCOL_TLS_CLIENT) -> None:
        """Load the certifi CA certificates."""
        super().__init__()
        self.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN | ssl.VERIFY_X509_STRICT
        self.load_verify_locations(cadata=_CERTIFI_CA_DATA)
        # Match ssl.create_default_context(), which httpx used
        if (keylogfile := environ.get("SSLKEYLOGFILE")) and not (
            sys.flags.ignore_environment
        ):
            self.keylog_filename = keylogfile


def setup_certifi_ssl_context() -> None:
    """Replace truststore.SSLContext with the certifi-backed context."""
    truststore.SSLContext = CertifiSSLContext  # type: ignore[misc,assignment]
