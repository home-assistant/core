"""Checker for tests that create a flow handler directly.

Integration tests should run a flow the way the frontend does: start it
with ``hass.config_entries.flow.async_init`` (or ``options`` /
``subentries``), answer its steps with ``async_configure`` and assert on the
results. Creating the integration's flow handler in the test skips the flow
manager: the context, unique ID handling, schema validation and the step
routing are never exercised, and the test ends up checking implementation
details instead.

``W7465`` (``home-assistant-tests-direct-flow-handler``)
"""

from astroid import AstroidError, nodes
from pylint.checkers import BaseChecker, utils
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import (
    is_integration_module,
    parse_module,
)

_FLOW_HANDLER = "homeassistant.data_entry_flow.FlowHandler"


def _flow_handler_name(call: nodes.Call) -> str | None:
    """Return the class name if *call* creates an integration flow handler."""
    inferred = utils.safe_infer(call.func)
    if not isinstance(inferred, nodes.ClassDef):
        return None
    if not is_integration_module(inferred.root().name):
        return None
    try:
        if not any(
            ancestor.qname() == _FLOW_HANDLER for ancestor in inferred.ancestors()
        ):
            return None
    except AstroidError:
        return None
    return str(inferred.name)


class DirectFlowHandlerChecker(BaseChecker):
    """Checker for tests that create a flow handler directly."""

    name = "home_assistant_tests_direct_flow_handler"
    priority = -1
    msgs = {
        "W7465": (
            "Do not create `%s` in tests; start the flow with `async_init` "
            "and continue it with `async_configure`",
            "home-assistant-tests-direct-flow-handler",
            "Used when an integration test creates an instance of a flow "
            "handler defined in an integration, such as its config, options, "
            "subentry or repair flow, instead of letting the flow manager "
            "create it.",
        ),
    }
    options = ()

    _in_integration_test: bool = False

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration test module."""
        self._in_integration_test = node.name.startswith("tests.") and (
            parse_module(node.name, include_test=True) is not None
        )

    def visit_call(self, node: nodes.Call) -> None:
        """Flag flow handler instantiation."""
        if not self._in_integration_test:
            return
        if (class_name := _flow_handler_name(node)) is not None:
            self.add_message(
                "home-assistant-tests-direct-flow-handler",
                node=node,
                args=(class_name,),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DirectFlowHandlerChecker(linter))
