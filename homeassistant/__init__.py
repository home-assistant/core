"""Init file for Home Assistant."""

from os import environ
import ssl

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


def _certifi_ssl_context(_protocol: int | None = None) -> ssl.SSLContext:
    """Return an SSL context verified against certifi, as httpx used to create."""
    return ssl.create_default_context(
        cafile=environ.get("REQUESTS_CA_BUNDLE", certifi.where())
    )


# httpx2 builds default SSL contexts with truststore, which on Linux reloads the
# system CA certificates on every TLS handshake, blocking the event loop. Use
# certifi instead, loaded once per context, consistent with the rest of HA.
truststore.SSLContext = _certifi_ssl_context  # type: ignore[misc,assignment]

# Probatio replaces voluptuous as the validation engine. Custom integrations and a
# few dependencies still import voluptuous directly, so alias it to probatio in
# sys.modules before anything imports it. This must run before the first
# `import voluptuous`, hence the package __init__.
install_as_voluptuous()

# Defer schema compilation until a schema is first validated. Home Assistant builds
# a large number of schemas, many of which are never validated in a given run, so
# lazy building avoids that upfront cost. Only the application may set this policy.
set_build_policy(BuildPolicy.LAZY)
