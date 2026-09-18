"""Checker to keep raw HTTP client usage out of integrations.

Integrations must not talk to their device or service directly with an HTTP
client. All device- and service-specific communication belongs in a library
published on PyPI, which is then added as a manifest requirement.

https://developers.home-assistant.io/docs/creating_component_code_review/#5-communication-with-devicesservices

The ``aiohttp`` server framework (``aiohttp.web``) is allowed, as it is used to
serve HTTP endpoints (views, webhooks) rather than to call out to a device or
service.

Integrations that already used a raw HTTP client before this check existed are
grandfathered in via ``GRANDFATHERED_DOMAINS``; that list must only shrink.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import parse_module
from pylint_home_assistant.http_library_exemptions import GRANDFATHERED_DOMAINS

_HTTP_CLIENT_LIBRARIES = frozenset({"aiohttp", "httpx", "requests"})


def _flagged_library(module: str, imported_names: list[str] | None) -> str | None:
    """Return the flagged HTTP client library for an import, or None.

    *module* is the dotted module being imported (e.g. ``aiohttp.client``).
    *imported_names* are the names imported from it for ``from`` imports
    (e.g. ``["ClientSession"]``), or None for plain ``import`` statements.
    """
    top, _, remainder = module.partition(".")
    if top not in _HTTP_CLIENT_LIBRARIES:
        return None

    if top != "aiohttp":
        return top

    # aiohttp.web is the server framework, not a client; always allowed.
    first_segment = remainder.partition(".")[0]
    if first_segment == "web":
        return None
    # ``from aiohttp import web`` is the server framework too.
    if module == "aiohttp" and imported_names is not None:
        if all(name == "web" for name in imported_names):
            return None

    return "aiohttp"


class HassEnforceHttpLibraryChecker(BaseChecker):
    """Checker that forbids raw HTTP client usage in integrations."""

    name = "hass_enforce_http_library"
    priority = -1
    msgs = {
        "W7438": (
            "Integration uses the `%s` HTTP client directly; device and service "
            "communication must go through a library published on PyPI",
            "hass-integration-raw-http-client",
            "Used when an integration imports `requests`, `httpx` or the "
            "`aiohttp` client instead of delegating device or service "
            "communication to a library hosted on PyPI.",
        ),
    }
    options = ()

    _check_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether the current module should be checked."""
        parsed = parse_module(node.name)
        self._check_module = (
            parsed is not None and parsed.domain not in GRANDFATHERED_DOMAINS
        )

    def visit_import(self, node: nodes.Import) -> None:
        """Check `import aiohttp`/`import requests` style imports."""
        if not self._check_module:
            return
        for name, _alias in node.names:
            if library := _flagged_library(name, None):
                self.add_message(
                    "hass-integration-raw-http-client", node=node, args=(library,)
                )
                return

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Check `from aiohttp import ClientSession` style imports."""
        if not self._check_module or node.level:
            return
        imported_names = [name for name, _alias in node.names]
        if library := _flagged_library(node.modname, imported_names):
            self.add_message(
                "hass-integration-raw-http-client", node=node, args=(library,)
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceHttpLibraryChecker(linter))
