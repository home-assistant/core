"""Init file for Home Assistant."""

from os import environ
import ssl
import sys
from typing import Self

import certifi
import httpx2
from probatio import BuildPolicy, set_build_policy
from probatio.compat import install_as_voluptuous
import truststore

# httpx2 replaces httpx as the HTTP client. Custom integrations and many
# dependencies still import httpx (and httpcore) directly, so alias them to
# httpx2 (and httpcore2) to share one set of classes and exceptions. This must
# run before the first `import httpx`, hence the package __init__.
httpx2.alias_httpx()


class _CertifiSSLContext(ssl.SSLContext):
    """Client SSL context verified against certifi, as httpx used to create."""

    def __new__(cls, protocol: int = ssl.PROTOCOL_TLS_CLIENT) -> Self:
        """Default to a client context, like truststore."""
        return super().__new__(cls, protocol)

    def __init__(self, protocol: int = ssl.PROTOCOL_TLS_CLIENT) -> None:
        """Load the certifi CA certificates."""
        super().__init__()
        self.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN | ssl.VERIFY_X509_STRICT
        self.load_verify_locations(cafile=certifi.where())
        # Match ssl.create_default_context(), which httpx used
        if (keylogfile := environ.get("SSLKEYLOGFILE")) and not (
            sys.flags.ignore_environment
        ):
            self.keylog_filename = keylogfile


# httpx2 defaults to truststore, which on Linux reloads the system CA store on
# every TLS handshake, blocking the event loop. Use certifi, like httpx did. A
# subclass keeps subclassing and isinstance checks on truststore working.
truststore.SSLContext = _CertifiSSLContext  # type: ignore[misc,assignment]

# Probatio replaces voluptuous as the validation engine. Custom integrations and a
# few dependencies still import voluptuous directly, so alias it to probatio in
# sys.modules before anything imports it. This must run before the first
# `import voluptuous`, hence the package __init__.
install_as_voluptuous()

# Defer schema compilation until a schema is first validated. Home Assistant builds
# a large number of schemas, many of which are never validated in a given run, so
# lazy building avoids that upfront cost. Only the application may set this policy.
set_build_policy(BuildPolicy.LAZY)
