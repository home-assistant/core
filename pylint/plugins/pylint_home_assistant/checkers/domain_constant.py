"""Plugin to encourage correct use of DOMAIN constants in tests."""

from dataclasses import dataclass

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module


@dataclass
class ArgumentCheckInfo:
    """Data class for argument check information."""

    position: int | None
    name: str
    allow_iterable: bool = False


_FUNCTION_CHECKS: list[tuple[str, ArgumentCheckInfo]] = [
    ("MockConfigEntry", ArgumentCheckInfo(None, "domain")),
    ("async_mock_service", ArgumentCheckInfo(1, "domain")),
    ("async_setup_component", ArgumentCheckInfo(1, "domain")),
]
_METHOD_CHECKS: list[tuple[str, str, ArgumentCheckInfo]] = [
    ("hass.config_entries.flow", "async_init", ArgumentCheckInfo(0, "handler")),
    ("hass.services", "async_call", ArgumentCheckInfo(0, "domain")),
    ("hass.services", "call", ArgumentCheckInfo(0, "domain")),
    ("hass.states", "async_entity_ids", ArgumentCheckInfo(0, "domain_filter", True)),
]

_DOMAIN_CONSTANTS: set[str] = {"DOMAIN", "domain"}
_DOMAIN_SUFFIXES: tuple[str, ...] = ("_DOMAIN", "_domain")


def _check_call_node_domain_arguments(node: nodes.Call) -> nodes.NodeNG | None:
    """Ensure the call node arguments are valid domain constant or variable.

    Return None if the argument node is valid, or the argument node if it is invalid.
    """
    match node.func:
        case nodes.Attribute():
            for method_source, method_name, arg_info in _METHOD_CHECKS:
                if (
                    node.func.attrname == method_name
                    and node.func.expr.as_string() == method_source
                ):
                    return _check_call_node_domain_argument(node, arg_info)
        case nodes.Name():
            for func_name, arg_info in _FUNCTION_CHECKS:
                if node.func.name == func_name:
                    return _check_call_node_domain_argument(node, arg_info)
    return None


def _check_call_node_domain_argument(
    call_node: nodes.Call, arg_info: ArgumentCheckInfo
) -> nodes.NodeNG | None:
    """Ensure the argument node is a domain constant or variable.

    Return None if the argument node is valid, or the argument node if it is invalid.
    """
    if arg_info.position is not None and len(call_node.args) > arg_info.position:
        argument_node = call_node.args[arg_info.position]
    else:
        argument_node = next(
            iter(
                keyword.value
                for keyword in call_node.keywords
                if keyword.arg == arg_info.name
            ),
            None,
        )

    if argument_node and not _check_domain_argument(
        argument_node, arg_info.allow_iterable
    ):
        return argument_node

    return None


def _check_domain_argument(arg_node: nodes.NodeNG, allow_iterable: bool) -> bool:
    """Ensure the argument node is a domain constant or variable.

    We allow:
        - x.DOMAIN/x.domain attribute (including *_DOMAIN/*_domain)
        - DOMAIN/domain name (including *_DOMAIN/*_domain)
        - string literals
        - subscript expressions (e.g. data["key"])

    Return True if the argument is valid, False otherwise.
    """
    match arg_node:
        case nodes.Attribute():
            if (
                attrname := arg_node.attrname
            ) in _DOMAIN_CONSTANTS or attrname.endswith(_DOMAIN_SUFFIXES):
                return True
        case nodes.Const():
            if isinstance(arg_node.value, str):
                return True
        case nodes.Name():
            if (node_name := arg_node.name) in _DOMAIN_CONSTANTS or node_name.endswith(
                _DOMAIN_SUFFIXES
            ):
                return True
        case nodes.Subscript():
            # Ignore subscripts like dict["key"]
            return True
        case nodes.Tuple():
            if allow_iterable:
                return all(
                    _check_domain_argument(element, allow_iterable=False)
                    for element in arg_node.elts
                )

    return False


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

    options = ()

    _in_test_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Visit Module node."""
        self._in_test_module = is_test_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Visit Call node."""
        if not self._in_test_module:
            return

        if invalid_arg_node := _check_call_node_domain_arguments(node):
            self.add_message(
                "home-assistant-domain-argument",
                node=invalid_arg_node,
                args=(invalid_arg_node.as_string(), node.func.as_string()),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DomainConstantChecker(linter))
