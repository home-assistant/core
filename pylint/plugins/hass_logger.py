"""Plugin for logger invocations."""
import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker
from pylint.lint import PyLinter

LOGGER_NAMES = ("LOGGER", "_LOGGER")
LOG_LEVEL_ALLOWED_LOWER_START = ("debug",)


class HassLoggerFormatChecker(BaseChecker):  # type: ignore[misc]
    """Checker for logger invocations."""

    __implements__ = IAstroidChecker

    name = "hass_logger"
    priority = -1
    msgs = {
        "W0001": (
            "User visible logger messages must not end with a period",
            "hass-logger-period",
            "Periods are not permitted at the end of logger messages",
        ),
        "W0002": (
            "User visible logger messages must start with a capital letter or downgrade to debug",
            "hass-logger-capital",
            "All logger messages must start with a capital letter",
        ),
    }
    options = ()

    def visit_call(self, node: astroid.Call) -> None:
        """Called when a Call node is visited."""
        if not isinstance(node.func, astroid.Attribute) or not isinstance(
            node.func.expr, astroid.Name
        ):
            return

        if not node.func.expr.name in LOGGER_NAMES:
            return

        if not node.args:
            return

        first_arg = node.args[0]

        if not isinstance(first_arg, astroid.Const) or not first_arg.value:
            return

        log_message = first_arg.value

        if len(log_message) < 1:
            return

        if log_message[-1] == ".":
            self.add_message("hass-logger-period", node=node)

        if (
            isinstance(node.func.attrname, str)
            and node.func.attrname not in LOG_LEVEL_ALLOWED_LOWER_START
            and log_message[0].upper() != log_message[0]
        ):
            self.add_message("hass-logger-capital", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassLoggerFormatChecker(linter))
