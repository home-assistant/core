"""Init file for Home Assistant."""

import httpx2
import probatio
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

# Probatio resolves its codec re-exports through a lazy import on first attribute
# access. Both of these are reached from the event loop, where that import is a
# blocking call: to_field_list renders every config flow form, to_openapi builds
# the tool schemas for a conversation turn. Resolve them here instead. It costs
# about 4 ms and pulls in no voluptuous of its own.
_ = probatio.to_field_list
_ = probatio.to_openapi

from .util.httpx2_ssl import setup_certifi_ssl_context  # noqa: E402

# httpx2 defaults to truststore, which blocks the event loop on TLS handshakes.
# Use certifi instead, like httpx did. See homeassistant/util/httpx2_ssl.py.
setup_certifi_ssl_context()
