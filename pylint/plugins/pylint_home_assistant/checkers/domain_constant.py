"""Plugin to encourage correct use of DOMAIN constants in tests."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module

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

_DOMAIN_CONSTANTS: set[str] = {"DOMAIN", "domain"}
_DOMAIN_SUFFIXES: tuple[str, ...] = ("_DOMAIN", "_domain")


def _check_call_node(checker: DomainConstantChecker, node: nodes.Call) -> None:
    """Visit Call node."""
    match node.func:
        case nodes.Attribute():
            for (
                method_source,
                method_name,
                arg_position,
                kwarg_name,
            ) in _METHOD_CHECKS:
                if (
                    node.func.attrname == method_name
                    and node.func.expr.as_string() == method_source
                ):
                    _check_call_node_arguments(
                        checker, node, arg_position=arg_position, kwarg_name=kwarg_name
                    )
                    return
        case nodes.Name():
            for func_name, arg_position, kwarg_name in _FUNCTION_CHECKS:
                if node.func.name == func_name:
                    _check_call_node_arguments(
                        checker, node, arg_position=arg_position, kwarg_name=kwarg_name
                    )
                    return


def _check_call_node_arguments(
    checker: DomainConstantChecker,
    call_node: nodes.Call,
    *,
    arg_position: int | None,
    kwarg_name: str,
) -> None:

    if arg_position is not None and len(call_node.args) > arg_position:
        _check_call_node_argument(checker, call_node, call_node.args[arg_position])
        return

    for keyword in call_node.keywords:
        if keyword.arg == kwarg_name:
            _check_call_node_argument(checker, call_node, keyword.value)
            return


def _check_call_node_argument(
    checker: DomainConstantChecker, call_node: nodes.Call, arg_node: nodes.NodeNG
) -> None:
    """Ensure the argument node is a domain constant or variable.

    We allow:
        - x.DOMAIN/x.domain attribute (including *_DOMAIN/*_domain)
        - DOMAIN/domain name (including *_DOMAIN/*_domain)
        - string literals (for cases where the constant is not imported)
        - subscript expressions (e.g. data["key"])
    """
    match arg_node:
        case nodes.Attribute():
            if (
                attrname := arg_node.attrname
            ) in _DOMAIN_CONSTANTS or attrname.endswith(_DOMAIN_SUFFIXES):
                return
        case nodes.Const():
            if isinstance(arg_node.value, str):
                return
        case nodes.Name():
            if (node_name := arg_node.name) in _DOMAIN_CONSTANTS or node_name.endswith(
                _DOMAIN_SUFFIXES
            ):
                return
        case nodes.Subscript():
            # Ignore subscripts like dict["key"]
            return

    checker.add_message(
        "home-assistant-domain-argument",
        node=arg_node,
        args=(arg_node.as_string(), call_node.func.as_string()),
    )


class DomainConstantChecker(BaseChecker):
    """Checker for correct use of DOMAIN constants in tests."""

    name = "home_assistant_domain_constant"
    priority = -1
    msgs = {
        "C7415": (
            "Argument %s should be a domain constant or variable in %s",
            "home-assistant-domain-argument",
            "Used when argument should be a domain constant/variable.",
        ),
    }

    _in_test_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Visit Module node."""
        self._in_test_module = is_test_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Visit Call node."""
        if not self._in_test_module:
            return

        _check_call_node(self, node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DomainConstantChecker(linter))
