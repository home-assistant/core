"""Checker for action registration outside ``services.py``.

Actions must be registered in the integration's ``services.py``, from
``async_setup_services`` (a synchronous ``@callback`` function called from
``async_setup``) or ``setup_services`` (a synchronous function, not a
``@callback``, called from ``setup``). Both only take ``hass``.
Module-level functions in ``services.py`` called from these functions may
register actions too.

This checker flags:
- action registrations anywhere else in an integration
- an ``async_setup_services`` or ``setup_services`` with a different signature

https://contributors.home-assistant.io/core/quality-scale/action-setup/
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import parse_module

# Setup function name and whether it must be a ``@callback``
_SETUP_FUNCTIONS = {
    "async_setup_services": True,
    "setup_services": False,
}

_REGISTRATION_FUNCTIONS = {
    "async_register_admin_service",
    "async_register_batched_entity_service",
    "async_register_batched_platform_entity_service",
    "async_register_entity_service",
    "async_register_platform_entity_service",
}


def _is_action_registration(node: nodes.Call) -> bool:
    """Return True if *node* registers an action."""
    match node.func:
        # hass.services.async_register(...) / hass.services.register(...)
        case nodes.Attribute(
            attrname="async_register" | "register",
            expr=nodes.Attribute(attrname="services"),
        ):
            return True
        case nodes.Name(name=name) | nodes.Attribute(attrname=name):
            return name in _REGISTRATION_FUNCTIONS
    return False


def _is_callback(node: nodes.FunctionDef) -> bool:
    """Return True if *node* is decorated with ``@callback``."""
    if node.decorators is None:
        return False
    return any(
        isinstance(decorator, (nodes.Name, nodes.Attribute))
        and (getattr(decorator, "name", None) or getattr(decorator, "attrname", None))
        == "callback"
        for decorator in node.decorators.nodes
    )


def _has_valid_signature(node: nodes.FunctionDef, callback: bool) -> bool:
    """Return True if *node* is a sync function taking only hass.

    *callback* tells whether it must or must not be a ``@callback``.
    """
    args = node.args
    return (
        not isinstance(node, nodes.AsyncFunctionDef)
        and _is_callback(node) is callback
        and [arg.name for arg in args.args] == ["hass"]
        and not args.posonlyargs
        and not args.kwonlyargs
        and args.vararg is None
        and args.kwarg is None
    )


def _allowed_functions(module: nodes.Module) -> set[str]:
    """Return the module-level functions allowed to register actions.

    These are the setup functions and the module-level functions they call,
    directly or indirectly.
    """
    functions = {
        child.name: child
        for child in module.body
        if isinstance(child, nodes.FunctionDef)
    }
    allowed: set[str] = set()
    pending = [name for name in _SETUP_FUNCTIONS if name in functions]
    while pending:
        name = pending.pop()
        if name in allowed:
            continue
        allowed.add(name)
        pending.extend(
            call.func.name
            for call in functions[name].nodes_of_class(nodes.Call)
            if isinstance(call.func, nodes.Name)
            and call.func.name in functions
            # Async helpers run later, e.g. when scheduled as a task
            and not isinstance(functions[call.func.name], nodes.AsyncFunctionDef)
        )
    return allowed


def _top_level_function(node: nodes.NodeNG) -> nodes.FunctionDef | None:
    """Return the module-level function containing *node*, if any."""
    scope: nodes.NodeNG = node
    while not isinstance(scope.parent, nodes.Module):
        if scope.parent is None:
            return None
        scope = scope.parent
    return scope if isinstance(scope, nodes.FunctionDef) else None


class ServicesModuleChecker(BaseChecker):
    """Checker for action registration outside ``services.py``."""

    name = "home_assistant_actions_services_module"
    priority = -1
    msgs = {
        "W7452": (
            "Action registered outside `async_setup_services` or "
            "`setup_services` in `services.py`",
            "home-assistant-action-registered-outside-services-module",
            "Used when an action is registered outside `async_setup_services` "
            "or `setup_services` in the integration's `services.py`, or the "
            "module-level functions they call.",
        ),
        "W7453": (
            "`%s` should be a synchronous function%s that only takes `hass`",
            "home-assistant-invalid-setup-services",
            "Used when `async_setup_services` or `setup_services` in "
            "`services.py` is a coroutine, takes other arguments than `hass`, "
            "or is (`setup_services`) or is not (`async_setup_services`) "
            "decorated with `@callback`.",
        ),
    }
    options = ()

    _in_integration: bool
    _allowed: set[str]

    def visit_module(self, node: nodes.Module) -> None:
        """Collect the functions allowed to register actions."""
        module = parse_module(node.name)
        self._in_integration = module is not None
        self._allowed = set()
        if module is None or module.module != "services":
            return
        self._allowed = _allowed_functions(node)
        for child in node.body:
            if (
                isinstance(child, nodes.FunctionDef)
                and (callback := _SETUP_FUNCTIONS.get(child.name)) is not None
                and not _has_valid_signature(child, callback)
            ):
                self.add_message(
                    "home-assistant-invalid-setup-services",
                    node=child,
                    args=(
                        child.name,
                        (" decorated" if callback else " not decorated")
                        + " with `@callback`",
                    ),
                )

    def visit_call(self, node: nodes.Call) -> None:
        """Check that actions are registered from async_setup_services."""
        if not self._in_integration or not _is_action_registration(node):
            return
        function = _top_level_function(node)
        if function is not None and function.name in self._allowed:
            return
        self.add_message(
            "home-assistant-action-registered-outside-services-module", node=node
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ServicesModuleChecker(linter))
