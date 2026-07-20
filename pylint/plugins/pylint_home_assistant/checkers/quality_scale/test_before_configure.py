"""Checker for the ``test-before-configure`` Bronze quality-scale rule.

**Quality-scale-gated**: only fires for integrations whose
``quality_scale.yaml`` marks ``test-before-configure`` as ``done``.

The config flow must test the connection with the user-provided data and
surface failures to the user before creating the entry. Testing cannot
be proven statically, so the checker looks for the footprint that
surfacing a failure always leaves behind, and fires when none is found:

- an ``errors=`` keyword passed to a call (e.g. ``async_show_form``)
  with a non-empty literal or any dynamic value, or
- an ``async_abort`` call or ``AbortFlow`` raise inside an ``except``
  handler (the catch-and-abort pattern of confirm-only flows).

A failure can only be surfaced if it was detected first, so this single
footprint covers the whole test-before-configure chain; flows that
detect failures but never show them to the user fail the check.

The footprint is searched in ``config_flow.py`` itself and in the
defining modules of inherited flow classes from other integrations
(e.g. the shared ``homeassistant_hardware`` firmware flow, which probes
the device before an entry can be created). Framework modules outside
``homeassistant.components`` are never treated as evidence.

Config flow classes inheriting ``AbstractOAuth2FlowHandler`` are
skipped: the OAuth token exchange is the connection test. Integrations
that rely on auto-discovery without user-provided connection data should
mark the rule ``exempt`` instead, per the rule's exceptions.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-configure/
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module, QualityScaleRule
from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.module_info import (
    get_module_platform,
    is_integration_module,
)
from pylint_home_assistant.helpers.quality_scale import quality_scale_rule_is_done

_CONFIG_FLOW_QNAME = "homeassistant.config_entries.ConfigFlow"
_OAUTH_FLOW_QNAME = (
    "homeassistant.helpers.config_entry_oauth2_flow.AbstractOAuth2FlowHandler"
)


def _is_surfacing_errors_value(value: nodes.NodeNG) -> bool:
    """Return True if the ``errors=`` value can show something to the user.

    A non-empty dict literal or any dynamic expression counts; an empty
    literal or ``None`` cannot surface anything.
    """
    match value:
        case nodes.Dict(items=items):
            return bool(items)
        case nodes.Const():
            return False
        case _:
            return True


def _handler_aborts(handler: nodes.ExceptHandler) -> bool:
    """Return True if the except handler aborts the flow."""
    for node in handler.nodes_of_class((nodes.Call, nodes.Raise)):
        match node:
            case nodes.Call(func=nodes.Attribute(attrname="async_abort")):
                return True
            case nodes.Raise(
                exc=nodes.Call(
                    func=nodes.Name(name="AbortFlow")
                    | nodes.Attribute(attrname="AbortFlow")
                )
            ):
                return True
    return False


def _module_surfaces_failures(module: nodes.Module) -> bool:
    """Return True if the module shows evidence of surfacing failures."""
    for node in module.nodes_of_class((nodes.Call, nodes.ExceptHandler)):
        match node:
            case nodes.ExceptHandler():
                if _handler_aborts(node):
                    return True
            case nodes.Call(keywords=keywords):
                if any(
                    keyword.arg == "errors"
                    and _is_surfacing_errors_value(keyword.value)
                    for keyword in keywords
                ):
                    return True
    return False


def _creates_entry(class_node: nodes.ClassDef) -> bool:
    """Return True if the class calls ``async_create_entry``."""
    return any(
        isinstance(call.func, nodes.Attribute)
        and call.func.attrname == "async_create_entry"
        for call in class_node.nodes_of_class(nodes.Call)
    )


class TestBeforeConfigureChecker(BaseChecker):
    """Checker for connection testing in config flow modules."""

    name = "home_assistant_test_before_configure"
    priority = -1
    msgs = {
        "W7433": (
            (
                "Config flow should test the connection with the user-provided "
                "data and show failures to the user before creating an entry "
                "(https://developers.home-assistant.io/docs/core/"
                "integration-quality-scale/rules/test-before-configure)"
            ),
            "home-assistant-missing-test-before-configure",
            (
                "Used when an integration marks test-before-configure as done "
                "but its config flow shows no evidence of surfacing connection "
                "failures to the user: no errors passed to async_show_form and "
                "no abort on a caught failure."
            ),
        ),
    }
    options = ()

    _check_module: bool
    _module_surfaces: bool

    def __init__(self, linter: PyLinter) -> None:
        """Initialize the checker and its ancestor module evidence cache."""
        super().__init__(linter)
        self._ancestor_surfaces: dict[str, bool] = {}

    def _ancestor_module_surfaces(self, module: nodes.Module) -> bool:
        """Check an inherited flow class's module for evidence, cached."""
        if module.name not in self._ancestor_surfaces:
            self._ancestor_surfaces[module.name] = _module_surfaces_failures(module)
        return self._ancestor_surfaces[module.name]

    def visit_module(self, node: nodes.Module) -> None:
        """Cache per-module gating and evidence scan results."""
        self._check_module = get_module_platform(
            node.name
        ) == Module.CONFIG_FLOW and quality_scale_rule_is_done(
            node, QualityScaleRule.TEST_BEFORE_CONFIGURE
        )
        self._module_surfaces = self._check_module and _module_surfaces_failures(node)

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Flag config flow classes that create entries without testing."""
        if not self._check_module or self._module_surfaces:
            return
        if not _creates_entry(node):
            return
        ancestors = list(extended_ancestors(node))
        ancestor_qnames = {a.qname() for a in ancestors}
        if (
            _CONFIG_FLOW_QNAME not in ancestor_qnames
            or _OAUTH_FLOW_QNAME in ancestor_qnames
        ):
            return
        for ancestor in ancestors:
            ancestor_module = ancestor.root()
            if (
                ancestor_module.name != node.root().name
                and is_integration_module(ancestor_module.name)
                and self._ancestor_module_surfaces(ancestor_module)
            ):
                return
        self.add_message("home-assistant-missing-test-before-configure", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(TestBeforeConfigureChecker(linter))
