"""Checker for logger message formatting and logger names.

Ensures logger messages start with a capital letter and do not end with a
period, enforcing a consistent style across the codebase.
Also ensures the logger defined in an integration's ``const.py`` is named
after the integration package.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import parse_module

LOGGER_NAMES = ("LOGGER", "_LOGGER")
LOG_LEVEL_ALLOWED_LOWER_START = ("debug",)


class HassLoggerFormatChecker(BaseChecker):
    """Checker for logger invocations."""

    name = "home_assistant_logger"
    priority = -1
    msgs = {
        "C7401": (
            "User visible logger messages must not end with a period",
            "home-assistant-logger-period",
            "Periods are not permitted at the end of logger messages",
        ),
        "C7402": (
            "User visible logger messages must start with a capital letter or downgrade to debug",
            "home-assistant-logger-capital",
            "All logger messages must start with a capital letter",
        ),
        "C7458": (
            "Logger in an integration const module should use __package__ instead of __name__",
            "home-assistant-logger-const-name",
            "The logger defined in an integration's const.py must be named after "
            "the integration package, not the const module",
        ),
    }
    options = ()

    _in_const_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Check if the module is an integration const module."""
        module = parse_module(node.name)
        self._in_const_module = (
            module is not None and node.name == f"{module.root}.{module.domain}.const"
        )

    def visit_call(self, node: nodes.Call) -> None:
        """Check for improper log messages and logger names."""
        if self._in_const_module:
            self._check_const_logger_name(node)

        if not isinstance(node.func, nodes.Attribute) or not isinstance(
            node.func.expr, nodes.Name
        ):
            return

        if node.func.expr.name not in LOGGER_NAMES:
            return

        if not node.args:
            return

        first_arg = node.args[0]

        if not isinstance(first_arg, nodes.Const) or not first_arg.value:
            return

        log_message = first_arg.value

        if len(log_message) < 1:
            return

        if log_message[-1] == ".":
            self.add_message("home-assistant-logger-period", node=node)

        if (
            isinstance(node.func.attrname, str)
            and node.func.attrname not in LOG_LEVEL_ALLOWED_LOWER_START
            and log_message[0].upper() != log_message[0]
        ):
            self.add_message("home-assistant-logger-capital", node=node)

    def _check_const_logger_name(self, node: nodes.Call) -> None:
        """Check that getLogger in a const module does not use __name__."""
        if isinstance(node.func, nodes.Attribute):
            func_name = node.func.attrname
        elif isinstance(node.func, nodes.Name):
            func_name = node.func.name
        else:
            return
        if func_name != "getLogger":
            return
        if node.args:
            name_node = node.args[0]
        else:
            name_node = next(
                (keyword.value for keyword in node.keywords if keyword.arg == "name"),
                None,
            )
        if isinstance(name_node, nodes.Name) and name_node.name == "__name__":
            self.add_message("home-assistant-logger-const-name", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassLoggerFormatChecker(linter))
