"""Init file for Home Assistant."""

import httpx2
from probatio import BuildPolicy, set_build_policy
from probatio.compat import install_as_voluptuous

# httpx2 replaces httpx as the HTTP client. Custom integrations and many
# dependencies still import httpx (and httpcore) directly, so alias them to
# httpx2 (and httpcore2) to share one set of classes and exceptions. This must
# run before the first `import httpx`, hence the package __init__.
httpx2.alias_httpx()

# Probatio replaces voluptuous as the validation engine. Custom integrations and a
# few dependencies still import voluptuous directly, so alias it to probatio in
# sys.modules before anything imports it. This must run before the first
# `import voluptuous`, hence the package __init__.
install_as_voluptuous()

# Defer schema compilation until a schema is first validated. Home Assistant builds
# a large number of schemas, many of which are never validated in a given run, so
# lazy building avoids that upfront cost. Only the application may set this policy.
set_build_policy(BuildPolicy.LAZY)

from .util.httpx2_ssl import setup_certifi_ssl_context  # noqa: E402

# httpx2 defaults to truststore, which blocks the event loop on TLS handshakes.
# Use certifi instead, like httpx did. See homeassistant/util/httpx2_ssl.py.
setup_certifi_ssl_context()
