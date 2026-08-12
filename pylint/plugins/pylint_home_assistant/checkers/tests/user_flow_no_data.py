"""Checker for ``data=`` in user config flow inits in tests.

In reality a user config flow is always started without any data — the
``data`` argument is only ever populated by discovery flows (zeroconf,
dhcp, ssdp, ...). Passing ``data`` to a user flow init in a test therefore
exercises a code path that cannot happen in production.

This checker flags calls of the form::

    hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={...},
    )

where the ``context`` source is the user source (``SOURCE_USER``,
``config_entries.SOURCE_USER`` or the literal ``"user"``) and a ``data``
keyword argument is supplied.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module

_SOURCE_USER = "SOURCE_USER"
_USER = "user"


def _context_source_is_user(context: nodes.NodeNG) -> bool:
    """Return True when the context dict's source is the user source."""
    if not isinstance(context, nodes.Dict):
        return False
    for key, value in context.items:
        if not (isinstance(key, nodes.Const) and key.value == "source"):
            continue
        if isinstance(value, nodes.Const):
            return value.value == _USER
        if isinstance(value, nodes.Name):
            return value.name == _SOURCE_USER
        if isinstance(value, nodes.Attribute):
            return value.attrname == _SOURCE_USER
        return False
    return False


class UserFlowNoDataChecker(BaseChecker):
    """Checker that forbids ``data=`` on user config flow inits in tests."""

    name = "home_assistant_tests_user_flow_no_data"
    priority = -1
    msgs = {
        "R7405": (
            "Do not pass `data` when initializing a user config flow; the "
            "user flow is always started without data in reality",
            "home-assistant-tests-user-flow-no-data",
            "Used when a test calls ``flow.async_init`` with a user source "
            "context and a ``data`` keyword argument. User flows never "
            "receive data in production — only discovery flows do.",
        ),
    }
    options = ()

    _active: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Record whether the module is a test module."""
        self._active = is_test_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Flag user flow inits that pass a ``data`` argument."""
        if not self._active:
            return

        func = node.func
        if not (isinstance(func, nodes.Attribute) and func.attrname == "async_init"):
            return

        context: nodes.NodeNG | None = None
        data: nodes.NodeNG | None = None
        for keyword in node.keywords or ():
            if keyword.arg == "context":
                context = keyword.value
            elif keyword.arg == "data":
                data = keyword.value

        if data is None or context is None:
            return

        if _context_source_is_user(context):
            self.add_message(
                "home-assistant-tests-user-flow-no-data",
                node=node,
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(UserFlowNoDataChecker(linter))
