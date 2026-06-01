"""Plugin to ensure correct use of constants."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

_FUNCTION_CHECKS: list[tuple[str, int | None, str]] = [
    ("async_setup_component", 1, "domain"),
    ("async_mock_service", 1, "domain"),
    ("MockConfigEntry", None, "domain"),
]
_METHOD_CHECKS: list[tuple[str, str, int | None, str]] = [
    ("hass.services", "async_call", 0, "domain"),
    ("hass.services", "call", 0, "domain"),
    ("hass.config_entries.flow", "async_init", 0, "handler"),
]


class HassEnforceConstantsChecker(BaseChecker):
    """Checker for correct use of constants."""

    name = "hass_enforce_constants"
    priority = -1
    msgs = {
        "C7414": (
            "Argument %s should be a domain constant or variable in %s",
            "hass-domain-argument",
            "Used when function/method argument should be a domain constant/variable.",
        ),
    }

    _in_test_module: bool
    _component: str | None

    def visit_module(self, node: nodes.Module) -> None:
        """Visit Module node."""
        self._in_test_module = node.name.startswith("tests.components.")
        self._component = node.name.split(".")[2] if self._in_test_module else None

    def visit_call(self, node: nodes.Call) -> None:
        """Visit Call node."""
        if not self._in_test_module:
            return

        if isinstance(node.func, nodes.Attribute):
            for method_source, method_name, arg_position, kwarg_name in _METHOD_CHECKS:
                if (
                    node.func.attrname == method_name
                    and node.func.expr.as_string() == method_source
                ):
                    self._ensure_domain_argument(
                        node, arg_position=arg_position, kwarg_name=kwarg_name
                    )
                    return
        if isinstance(node.func, nodes.Name):
            for func_name, arg_position, kwarg_name in _FUNCTION_CHECKS:
                if node.func.name == func_name:
                    self._ensure_domain_argument(
                        node, arg_position=arg_position, kwarg_name=kwarg_name
                    )
                    return

    def _ensure_domain_argument(
        self, call_node: nodes.Call, *, arg_position: int | None, kwarg_name: str
    ) -> None:

        if arg_position is not None and len(call_node.args) > arg_position:
            self._ensure_domain_argument_node(call_node, call_node.args[arg_position])

        for keyword in call_node.keywords:
            if keyword.arg == kwarg_name:
                self._ensure_domain_argument_node(call_node, keyword.value)
                return

    def _ensure_domain_argument_node(
        self, call_node: nodes.Call, arg_node: nodes.Argument | nodes.Keyword
    ) -> None:
        """Ensure the argument node is a domain constant or variable.

        We allow:
         - DOMAIN constant (or x.DOMAIN attribute)
         - domain variable (or x.domain attribute)
         - constants ending with _DOMAIN
         - variables ending with _domain
        """
        match arg_node:
            case nodes.Attribute():
                if arg_node.attrname in {"DOMAIN", "domain"}:
                    self.add_message(
                        "hass-domain-argument",
                        node=arg_node,
                        args=(arg_node.as_string(), call_node.func.as_string()),
                    )
                return
            case nodes.Name():
                if (
                    (node_name := arg_node.name) not in {"DOMAIN", "domain"}
                    and not node_name.endswith("_DOMAIN")
                    and not node_name.endswith("_domain")
                ):
                    self.add_message(
                        "hass-domain-argument",
                        node=arg_node,
                        args=(arg_node.as_string(), call_node.func.as_string()),
                    )
                return


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConstantsChecker(linter))
