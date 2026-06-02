"""Checker that flags raising exception classes from third-party libraries.

Exceptions raised inside Home Assistant integrations should be either
Python built-in/stdlib exceptions (``ValueError`` etc.), exceptions from
``homeassistant.*`` (``HomeAssistantError``, ``ConfigEntryNotReady``,
``UpdateFailed``, ...), or exceptions defined locally in the integration
itself. Raising an exception class that lives in a third-party dependency
leaks that dependency's type into Home Assistant's public surface (e.g.
service-call errors), making the integration harder to reason about and
the API harder to keep stable.

Two framework-level libraries are explicitly allowed because raising one
of their exception classes is the documented idiomatic pattern:

* ``voluptuous`` -- HA's validation library; raising ``vol.Invalid`` is
  how validators signal failure.
* ``aiohttp.web`` / ``aiohttp.web_exceptions`` -- raising
  ``web.HTTPNotFound`` etc. is how aiohttp handlers return HTTP
  responses.

Bare ``raise`` (re-raising the currently caught exception) is always
fine; this checker only flags raises that explicitly name a class.
"""

import functools
import sys

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module

_STDLIB_MODULES = sys.stdlib_module_names

# Top-level module names whose exception classes are allowed to be raised
# directly because raising them is the documented framework pattern.
_ALLOWED_TOP_LEVEL = frozenset({"voluptuous"})

# Fully-qualified module prefixes under ``aiohttp`` that are allowed in
# addition to the top-level allowlist above.  Anything imported from one
# of these modules (or a sub-module) may be raised.
_ALLOWED_MODULE_PREFIXES = ("aiohttp.web", "aiohttp.web_exceptions")


@functools.cache
def _is_third_party(module_name: str) -> bool:
    """Return True if *module_name* is a third-party (non-stdlib, non-HA) module."""
    if not module_name:
        return False
    top = module_name.partition(".")[0]
    if top in _STDLIB_MODULES or top == "homeassistant" or top in _ALLOWED_TOP_LEVEL:
        return False
    if top != "aiohttp":
        return True
    return not any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in _ALLOWED_MODULE_PREFIXES
    )


def _top_attribute_name(node: nodes.NodeNG) -> str | None:
    """Return the left-most ``Name`` in an Attribute chain, else ``None``."""
    current: nodes.NodeNG = node
    while isinstance(current, nodes.Attribute):
        current = current.expr
    if isinstance(current, nodes.Name):
        return str(current.name)
    return None


class HassRaiseThirdPartyChecker(BaseChecker):
    """Flag ``raise X(...)`` where ``X`` is imported from a third-party library."""

    name = "home_assistant_raise_third_party"
    priority = -1
    msgs = {
        "W7423": (
            "Do not raise third-party exception '%s' (from '%s'); raise a "
            "built-in exception, a HomeAssistantError subclass, or an "
            "integration-local exception instead",
            "home-assistant-raise-third-party-exception",
            "Used when ``raise X(...)`` is called with an exception class "
            "imported from a third-party library. Integrations should "
            "translate third-party errors into stdlib exceptions, "
            "``HomeAssistantError`` subclasses, or integration-local "
            "exception types rather than re-raising the library's own "
            "exception class.",
        ),
    }
    options = ()

    _enabled: bool
    # Map of local-binding name -> source module (e.g. ``HoleError`` ->
    # ``hole.exceptions``) for names brought in via ``from X import Y``.
    _from_imports: dict[str, str]
    # Map of local-binding name -> imported module (e.g. ``gpio`` ->
    # ``numato_gpio``) for names brought in via ``import X [as Y]``.
    _module_imports: dict[str, str]

    def visit_module(self, node: nodes.Module) -> None:
        """Reset state and collect third-party imports at module level."""
        self._from_imports = {}
        self._module_imports = {}
        self._enabled = is_integration_module(node.name)
        if not self._enabled:
            return

        for stmt in node.body:
            match stmt:
                case nodes.ImportFrom(modname=modname, names=names, level=level):
                    # Skip relative imports (level > 0) — those reference
                    # integration-local code, never third-party.
                    if level or not _is_third_party(modname):
                        continue
                    for name, alias in names:
                        if name == "*":
                            continue
                        self._from_imports[alias or name] = modname
                case nodes.Import(names=names):
                    for name, alias in names:
                        if not _is_third_party(name):
                            continue
                        self._module_imports[alias or name] = name

    def visit_raise(self, node: nodes.Raise) -> None:
        """Flag raises whose exception type is third-party."""
        if not self._enabled or node.exc is None:
            return

        # ``raise X(...)`` -> inspect ``X``; ``raise X`` -> ``node.exc`` is X.
        target = node.exc.func if isinstance(node.exc, nodes.Call) else node.exc

        match target:
            case nodes.Name(name=name) if name in self._from_imports:
                self.add_message(
                    "home-assistant-raise-third-party-exception",
                    node=node,
                    args=(name, self._from_imports[name]),
                )
            case nodes.Attribute():
                top = _top_attribute_name(target)
                if top is None or top not in self._module_imports:
                    return
                # Walk the attribute chain; ``attrs`` ends up outer-to-inner,
                # so the first element is the class name and the rest are
                # intermediate sub-modules (e.g. for
                # ``aiohttp.web_exceptions.HTTPMethodNotAllowed`` we get
                # ``["HTTPMethodNotAllowed", "web_exceptions"]``).
                attrs: list[str] = []
                cur: nodes.NodeNG = target
                while isinstance(cur, nodes.Attribute):
                    attrs.append(cur.attrname)
                    cur = cur.expr
                top_module = self._module_imports[top]
                resolved_module = ".".join([top_module, *reversed(attrs[1:])])
                # Reuse the cached classifier so the allowed-prefix list
                # only lives in one place.
                if not _is_third_party(resolved_module):
                    return
                dotted = ".".join([top, *reversed(attrs)])
                self.add_message(
                    "home-assistant-raise-third-party-exception",
                    node=node,
                    args=(dotted, top_module),
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassRaiseThirdPartyChecker(linter))
