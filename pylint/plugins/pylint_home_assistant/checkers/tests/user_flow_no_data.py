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
keyword argument is supplied. Both the config-entry flow manager
(``config_entries.flow``) and the subentry flow manager
(``config_entries.subentries``) are covered, and the ``context`` may be a
dict literal or a ``ConfigFlowContext(source=...)`` call.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module

_SOURCE_USER = "SOURCE_USER"
_USER = "user"
_FLOW_MANAGERS = frozenset({"flow", "subentries"})
_CONFIG_FLOW_CONTEXT = "ConfigFlowContext"


def _source_value_is_user(value: nodes.NodeNG) -> bool:
    """Return True when a ``source`` value refers to the user source."""
    if isinstance(value, nodes.Const):
        return bool(value.value == _USER)
    if isinstance(value, nodes.Name):
        return bool(value.name == _SOURCE_USER)
    if isinstance(value, nodes.Attribute):
        return bool(value.attrname == _SOURCE_USER)
    return False


def _context_source_is_user(context: nodes.NodeNG) -> bool:
    """Return True when the context's source is the user source.

    Handles both a dict literal (``{"source": SOURCE_USER}``) and a
    ``ConfigFlowContext(source=SOURCE_USER)`` call.
    """
    if isinstance(context, nodes.Dict):
        for key, value in context.items:
            if isinstance(key, nodes.Const) and key.value == "source":
                return _source_value_is_user(value)
        return False

    if isinstance(context, nodes.Call):
        func = context.func
        name = (
            func.attrname
            if isinstance(func, nodes.Attribute)
            else func.name
            if isinstance(func, nodes.Name)
            else None
        )
        if name != _CONFIG_FLOW_CONTEXT:
            return False
        for keyword in context.keywords or ():
            if keyword.arg == "source":
                return _source_value_is_user(keyword.value)

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
            "Used when a test calls ``flow.async_init`` or "
            "``subentries.async_init`` with a user source context and a "
            "``data`` keyword argument. User flows never receive data in "
            "production — only discovery flows do.",
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

        # Only the config-entry flow managers, i.e. ``*.flow.async_init`` and
        # ``*.subentries.async_init``. This avoids flagging unrelated
        # ``async_init`` methods that happen to take ``context``/``data``.
        manager = func.expr
        if not (
            isinstance(manager, nodes.Attribute) and manager.attrname in _FLOW_MANAGERS
        ):
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
