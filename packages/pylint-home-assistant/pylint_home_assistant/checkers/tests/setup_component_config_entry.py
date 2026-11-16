"""Checker for tests that set up a config entry only integration as a component.

An integration with a config flow that doesn't accept YAML configuration only
sets up its config entries when ``async_setup_component`` is called for it.
Tests should then set up the config entry directly:

.. code-block:: python

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

Only modules in ``tests/components/<domain>/`` are checked, and only calls
that set up ``<domain>`` itself. The integration doesn't accept YAML when its
``__init__`` module has no ``async_setup``, or sets ``CONFIG_SCHEMA`` with
``cv.config_entry_only_config_schema`` or ``cv.empty_config_schema``.
"""

import json
from pathlib import Path

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.checkers.utils import safe_infer
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.integration import get_tested_integration_dir
from pylint_home_assistant.helpers.module_info import is_test_module

_CONFIG_ENTRY_ONLY_SCHEMAS = frozenset(
    {"config_entry_only_config_schema", "empty_config_schema"}
)

_config_entry_only_cache: dict[Path, bool] = {}


def _has_config_flow(integration_dir: Path) -> bool:
    """Return True if the integration's manifest enables the config flow."""
    try:
        manifest = json.loads((integration_dir / "manifest.json").read_text())
    except OSError, ValueError:
        return False
    return manifest.get("config_flow") is True


def _accepts_yaml(init_module: nodes.Module) -> bool:
    """Return True if the integration's ``__init__`` accepts YAML configuration."""
    has_async_setup = False
    for node in init_module.body:
        match node:
            case (
                nodes.AsyncFunctionDef(name="async_setup")
                | nodes.FunctionDef(name="async_setup")
            ):
                has_async_setup = True
            case nodes.Assign(
                targets=[nodes.AssignName(name="CONFIG_SCHEMA")],
                value=nodes.Call(
                    func=nodes.Attribute(attrname=schema) | nodes.Name(name=schema)
                ),
            ) if schema in _CONFIG_ENTRY_ONLY_SCHEMAS:
                return False
    return has_async_setup


def _is_config_entry_only(integration_dir: Path) -> bool:
    """Return True if the integration is set up through config entries only."""
    if integration_dir in _config_entry_only_cache:
        return _config_entry_only_cache[integration_dir]

    result = False
    if _has_config_flow(integration_dir):
        try:
            init_module = astroid.parse((integration_dir / "__init__.py").read_text())
        except OSError, astroid.AstroidSyntaxError:
            pass
        else:
            result = not _accepts_yaml(init_module)

    _config_entry_only_cache[integration_dir] = result
    return result


def _is_async_setup_component(call: nodes.Call) -> bool:
    """Return True for a call to ``async_setup_component``."""
    match call.func:
        case (
            nodes.Name(name="async_setup_component")
            | nodes.Attribute(attrname="async_setup_component")
        ):
            return True
    return False


def _domain_arg(call: nodes.Call) -> nodes.NodeNG | None:
    """Return the ``domain`` argument of an ``async_setup_component`` call."""
    if len(call.args) > 1:
        return call.args[1]
    for keyword in call.keywords:
        if keyword.arg == "domain":
            return keyword.value
    return None


def _is_domain(node: nodes.NodeNG, domain: str) -> bool:
    """Return True if *node* evaluates to *domain*.

    A ``DOMAIN`` constant that can't be inferred is assumed to be the domain of
    the tested integration.
    """
    inferred = safe_infer(node)
    if isinstance(inferred, nodes.Const):
        return bool(inferred.value == domain)
    match node:
        case nodes.Name(name="DOMAIN") | nodes.Attribute(attrname="DOMAIN"):
            return True
    return False


class SetupComponentConfigEntry(BaseChecker):
    """Checker for tests that set up a config entry only integration as a component."""

    name = "home_assistant_tests_setup_component_config_entry"
    priority = -1
    msgs = {
        "W7465": (
            "`%s` is only set up through config entries, set up the config "
            "entry with `hass.config_entries.async_setup(entry.entry_id)` "
            "instead of `async_setup_component`",
            "home-assistant-tests-setup-component-config-entry",
            "Used when a test sets up an integration that has a config flow "
            "and doesn't accept YAML configuration with "
            "`async_setup_component`, instead of setting up its config entry.",
        ),
    }
    options = ()

    _domain: str | None = None

    def visit_module(self, node: nodes.Module) -> None:
        """Record the tested integration if it's only set up by config entries."""
        self._domain = None
        if not is_test_module(node.name):
            return
        integration_dir = get_tested_integration_dir(node)
        if integration_dir is not None and _is_config_entry_only(integration_dir):
            self._domain = integration_dir.name

    def visit_call(self, node: nodes.Call) -> None:
        """Flag ``async_setup_component`` calls for the tested integration."""
        if (
            self._domain is None
            or not _is_async_setup_component(node)
            or (domain_arg := _domain_arg(node)) is None
            or not _is_domain(domain_arg, self._domain)
        ):
            return
        self.add_message(
            "home-assistant-tests-setup-component-config-entry",
            node=node,
            args=(self._domain,),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(SetupComponentConfigEntry(linter))
