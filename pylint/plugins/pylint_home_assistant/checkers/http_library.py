"""Checker to keep raw HTTP requests out of integrations.

Integrations must not talk to their device or service directly with an HTTP
client. All device- and service-specific communication belongs in a library
published on PyPI, which is then added as a manifest requirement.

https://developers.home-assistant.io/docs/creating_component_code_review/#5-communication-with-devicesservices

This flags *making* requests and *creating* a client session with ``requests``,
``httpx`` or ``aiohttp`` (e.g. ``requests.get(...)``, ``httpx.AsyncClient(...)``,
``aiohttp.ClientSession(...)``). It deliberately does not flag imports used only
for typing or exception handling: type-hinting an injected
``aiohttp.ClientSession`` and catching ``aiohttp.ClientError`` are good practice.

Integrations that already made raw requests before this check existed are
grandfathered in via ``GRANDFATHERED_DOMAINS``; that list must only shrink.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import parse_module
from pylint_home_assistant.http_library_exemptions import GRANDFATHERED_DOMAINS

_REQUEST_METHODS = frozenset(
    {"request", "get", "post", "put", "patch", "delete", "head", "options"}
)
# Callables per library that perform a request or create a client session.
_FLAGGED_OPERATIONS: dict[str, frozenset[str]] = {
    "requests": _REQUEST_METHODS | {"Session"},
    "httpx": _REQUEST_METHODS | {"stream", "Client", "AsyncClient"},
    "aiohttp": frozenset({"ClientSession", "request"}),
}


class HassEnforceHttpLibraryChecker(BaseChecker):
    """Checker that forbids raw HTTP requests in integrations."""

    name = "hass_enforce_http_library"
    priority = -1
    msgs = {
        "W7438": (
            "Integration makes raw HTTP requests with `%s`; device and service "
            "communication must go through a library published on PyPI",
            "hass-integration-raw-http-client",
            "Used when an integration makes requests or creates a client session "
            "with `requests`, `httpx` or `aiohttp` instead of delegating device "
            "or service communication to a library hosted on PyPI.",
        ),
    }
    options = ()

    _check_module: bool
    _module_aliases: dict[str, str]
    _imported_callables: dict[str, str]

    def visit_module(self, node: nodes.Module) -> None:
        """Reset per-module state and decide whether to check the module."""
        parsed = parse_module(node.name)
        self._check_module = (
            parsed is not None and parsed.domain not in GRANDFATHERED_DOMAINS
        )
        # Local name -> library for `import requests`/`import aiohttp`.
        self._module_aliases = {}
        # Local name -> library for `from requests import get`.
        self._imported_callables = {}

    def visit_import(self, node: nodes.Import) -> None:
        """Track `import requests`/`import aiohttp as x` bindings."""
        if not self._check_module:
            return
        for name, alias in node.names:
            parts = name.split(".")
            library = parts[0]
            if library not in _FLAGGED_OPERATIONS:
                continue
            if len(parts) == 1:
                self._module_aliases[alias or name] = library
            elif alias is None:
                # e.g. `import aiohttp.web` also binds the top-level package.
                self._module_aliases[library] = library

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Track `from requests import get` style bindings."""
        if not self._check_module or node.level:
            return
        library = node.modname.split(".")[0]
        if library not in _FLAGGED_OPERATIONS:
            return
        flagged = _FLAGGED_OPERATIONS[library]
        for name, alias in node.names:
            if name in flagged:
                self._imported_callables[alias or name] = library

    def visit_call(self, node: nodes.Call) -> None:
        """Flag calls that make a request or create a client session."""
        if not self._check_module:
            return
        func = node.func
        if isinstance(func, nodes.Attribute):
            expr = func.expr
            if (
                isinstance(expr, nodes.Name)
                and (library := self._module_aliases.get(expr.name))
                and func.attrname in _FLAGGED_OPERATIONS[library]
            ):
                self.add_message(
                    "hass-integration-raw-http-client", node=node, args=(library,)
                )
        elif isinstance(func, nodes.Name):
            if library := self._imported_callables.get(func.name):
                self.add_message(
                    "hass-integration-raw-http-client", node=node, args=(library,)
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceHttpLibraryChecker(linter))
