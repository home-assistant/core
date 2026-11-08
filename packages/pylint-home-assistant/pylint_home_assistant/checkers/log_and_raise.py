"""Checker for logging an error right before raising it to Home Assistant.

Home Assistant already reports the exceptions an integration raises to it:
config entry setup logs ``ConfigEntryNotReady``, ``ConfigEntryAuthFailed`` and
``ConfigEntryError``, a coordinator logs ``UpdateFailed``, and a failing action
returns ``HomeAssistantError`` to the caller. Logging the same error first
reports it twice.

``W7450`` (``home-assistant-log-and-raise``)
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module

_REPORTED_EXCEPTIONS = {
    "homeassistant.exceptions.ConfigEntryAuthFailed",
    "homeassistant.exceptions.ConfigEntryError",
    "homeassistant.exceptions.ConfigEntryNotReady",
    "homeassistant.exceptions.HomeAssistantError",
    "homeassistant.exceptions.ServiceValidationError",
    "homeassistant.helpers.update_coordinator.UpdateFailed",
}
_LOG_LEVELS = {"critical", "error", "exception", "warning"}


def _reported_exception(node: nodes.Raise) -> str | None:
    """Return the name of the raised exception if Home Assistant reports it."""
    exc = node.exc.func if isinstance(node.exc, nodes.Call) else node.exc
    if exc is None:
        return None
    try:
        for inferred in exc.infer():
            if (
                isinstance(inferred, (nodes.ClassDef, astroid.Instance))
                and inferred.qname() in _REPORTED_EXCEPTIONS
            ):
                return str(inferred.name)
    except astroid.exceptions.InferenceError:
        pass
    return None


def _is_log_call(node: nodes.NodeNG) -> bool:
    """Return True for a ``logger.error(...)`` like statement."""
    match node:
        case nodes.Expr(
            value=nodes.Call(
                func=nodes.Attribute(
                    attrname=level,
                    expr=nodes.Name(name=name) | nodes.Attribute(attrname=name),
                )
            )
        ) if level in _LOG_LEVELS and name.lower().endswith("logger"):
            return True
    return False


class LogAndRaiseChecker(BaseChecker):
    """Checker for logging an error right before raising it."""

    name = "home_assistant_log_and_raise"
    priority = -1
    msgs = {
        "W7450": (
            "Don't log before raising `%s`, Home Assistant already reports it",
            "home-assistant-log-and-raise",
            (
                "Used when an integration logs an error and then raises an "
                "exception that Home Assistant reports itself, such as "
                "`UpdateFailed`, `ConfigEntryNotReady` or `HomeAssistantError`."
            ),
        ),
    }
    options = ()

    _in_integration = False

    def visit_module(self, node: nodes.Module) -> None:
        """Only check integration modules."""
        self._in_integration = is_integration_module(node.name)

    def visit_raise(self, node: nodes.Raise) -> None:
        """Check for a log call earlier in the block of the raise."""
        if not self._in_integration or (name := _reported_exception(node)) is None:
            return

        sibling = node.previous_sibling()
        while sibling is not None:
            if _is_log_call(sibling):
                self.add_message(
                    "home-assistant-log-and-raise", node=sibling, args=(name,)
                )
                return
            sibling = sibling.previous_sibling()


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(LogAndRaiseChecker(linter))
