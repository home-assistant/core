import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker

LOGGER_NAMES = ("LOGGER", "_LOGGER")
LOG_LEVEL_ALLOWED_LOWER_START = ("debug",)

# This is our checker class.
# Checkers should always inherit from `BaseChecker`.
class HassLoggerFormatChecker(BaseChecker):
    """Add class member attributes to the class locals dictionary."""

    __implements__ = IAstroidChecker

    # The name defines a custom section of the config for this checker.
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
    options = (
        (
            "hass-logger",
            {
                "default": "properties",
                "help": (
                    "Validate _LOGGER or LOGGER messages conform to Home Assistant standards."
                ),
            },
        ),
    )

    def visit_call(self, node):
        """Called when a :class:`.astroid.node_classes.Call` node is visited.
        See :mod:`astroid` for the description of available nodes.
        :param node: The node to check.
        :type node: astroid.node_classes.Call
        """
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
            self.add_message("hass-logger-period", args=node.args, node=node)

        if (
            isinstance(node.func.attrname, str)
            and node.func.attrname not in LOG_LEVEL_ALLOWED_LOWER_START
            and log_message[0].upper() != log_message[0]
        ):
            self.add_message("hass-logger-capital", args=node.args, node=node)


def register(linter):
    """This required method auto registers the checker.
    :param linter: The linter to register the checker to.
    :type linter: pylint.lint.PyLinter
    """
    linter.register_checker(HassLoggerFormatChecker(linter))
