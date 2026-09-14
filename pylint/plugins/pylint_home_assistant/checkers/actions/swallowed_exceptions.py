"""Checker for swallowed exceptions in action handlers.

Service/action handlers in integrations must not silently swallow
exceptions. If an action handler catches a library exception and only
logs it (or suppresses it via ``contextlib.suppress``), the user gets
no feedback in the UI when the action fails.

This checker detects suppression only — it does not validate *what*
exception type is raised. A separate checker should verify that raised
exceptions are ``HomeAssistantError`` subclasses with proper translations.

This rule only applies to modules inside ``homeassistant.components.*``,
not to test code or core framework code.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from .helpers import ActionHandlers, collect_action_handlers


def _except_block_swallows(handler: nodes.ExceptHandler) -> bool:
    """Return True if the except block swallows the exception.

    Flags blocks that:
    - Are empty (just ``pass``)
    - Call ``_LOGGER.error/exception/warning`` and nothing else
    - Log then ``return`` (silently swallowing the error)

    Does NOT flag blocks that:
    - Contain a ``raise`` statement (any kind)
    """
    has_log_call = False
    has_any_statement = False
    for child in handler.body:
        if isinstance(child, nodes.Raise):
            return False
        if isinstance(child, nodes.Pass):
            continue
        has_any_statement = True
        if isinstance(child, nodes.Expr) and isinstance(child.value, nodes.Call):
            call = child.value
            if (
                isinstance(call.func, nodes.Attribute)
                and call.func.attrname in ("error", "exception", "warning")
                and isinstance(call.func.expr, nodes.Name)
                and call.func.expr.name in ("_LOGGER", "LOGGER")
            ):
                has_log_call = True
                continue
        if isinstance(child, nodes.Return) and has_log_call:
            return True

    # Empty body (just pass) or log-only body
    return not has_any_statement or has_log_call


def _is_contextlib_suppress(node: nodes.NodeNG) -> bool:
    """Return True if *node* is a ``contextlib.suppress(...)`` call.

    Only matches ``contextlib.suppress(...)`` (attribute access form),
    not a bare ``suppress(...)`` which could be an unrelated function.
    """
    if not isinstance(node, nodes.Call):
        return False
    return (
        isinstance(node.func, nodes.Attribute)
        and node.func.attrname == "suppress"
        and isinstance(node.func.expr, nodes.Name)
        and node.func.expr.name == "contextlib"
    )


def _is_action_handler(node: nodes.FunctionDef, handlers: ActionHandlers) -> bool:
    """Return True if *node* is a registered action handler.

    Platform action methods are scoped by module (the ``ActionHandlers``
    only contains methods for the current platform), so any method on a
    class with base classes is accepted. Dynamically registered handlers
    can be standalone functions or methods on any class.
    """
    if isinstance(node.parent, nodes.ClassDef):
        # Method on a class — accept if name matches platform or registered
        # handlers AND the class has base classes (not a plain helper class)
        if node.name in handlers.platform_methods:
            return bool(node.parent.bases)
        return node.name in handlers.registered_handlers
    # Standalone function — only valid if dynamically registered
    return node.name in handlers.registered_handlers


def _check_body_shallow(
    body: list[nodes.NodeNG],
) -> nodes.NodeNG | None:
    """Check a function body for swallowed exceptions, non-recursively.

    Checks try/except and contextlib.suppress at the current nesting level
    and inside control flow (if/for/while/with), but does NOT recurse
    into nested function definitions.

    Returns the first offending node, or None.
    """
    for child in body:
        if isinstance(child, nodes.Try):
            for handler in child.handlers:
                if _except_block_swallows(handler):
                    return handler
        elif isinstance(child, (nodes.With, nodes.AsyncWith)):
            # Check the context manager for contextlib.suppress
            for ctx, _ in child.items:
                if _is_contextlib_suppress(ctx):
                    return child
            # Also recurse into the with body for try/except blocks
            result = _check_body_shallow(child.body)
            if result:
                return result
        elif isinstance(child, nodes.If):
            result = _check_body_shallow(child.body) or _check_body_shallow(
                child.orelse
            )
            if result:
                return result
        elif isinstance(child, (nodes.For, nodes.AsyncFor, nodes.While)):
            result = _check_body_shallow(child.body)
            if result:
                return result
    return None


class SwallowedActionExceptionsChecker(BaseChecker):
    """Checker for swallowed exceptions in service action handlers."""

    name = "home_assistant_actions_swallowed_exceptions"
    priority = -1
    msgs = {
        "E7405": (
            "Exception in '%s' is swallowed — the error is not raised, "
            "so the user will not be notified of the failure",
            "home-assistant-action-swallowed-exception",
            "Used when a service action handler catches an exception but "
            "only logs it or suppresses it instead of re-raising. The user "
            "needs to see the error in the UI.",
        ),
    }
    options = ()

    _action_handlers: ActionHandlers

    def visit_module(self, node: nodes.Module) -> None:
        """Determine which action handlers to check for this module."""
        self._action_handlers = collect_action_handlers(node)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check action handlers for swallowed exceptions."""
        if not self._action_handlers.all_names:
            return

        if not _is_action_handler(node, self._action_handlers):
            return

        # Check the function body (shallow — no nested function defs)
        if offending := _check_body_shallow(node.body):
            self.add_message(
                "home-assistant-action-swallowed-exception",
                node=offending,
                args=(node.name,),
            )

        # Check decorators — they may wrap the function and swallow exceptions
        if node.decorators:
            for decorator in node.decorators.nodes:
                self._check_decorator(node, decorator)

    visit_asyncfunctiondef = visit_functiondef

    def _check_decorator(
        self, node: nodes.FunctionDef, decorator: nodes.NodeNG
    ) -> None:
        """Check if a decorator swallows exceptions.

        Uses astroid's inference to resolve the decorator function — works
        across modules (e.g., a decorator imported from ``entity.py``).
        Only checks decorators defined in ``homeassistant`` code, not
        stdlib or third-party decorators.
        """
        infer_node = decorator
        if isinstance(decorator, nodes.Call):
            infer_node = decorator.func

        try:
            for inferred in infer_node.infer():
                if not isinstance(inferred, nodes.FunctionDef):
                    continue
                # Skip decorators not defined in homeassistant code
                # (stdlib decorators like @final, @override, @cache have
                # internal try/except that would cause false positives)
                module_name = inferred.root().name
                if not module_name.startswith("homeassistant."):
                    continue
                if _decorator_swallows(inferred):
                    self.add_message(
                        "home-assistant-action-swallowed-exception",
                        node=decorator,
                        args=(node.name,),
                    )
                    return
        except Exception:  # noqa: BLE001
            pass


def _decorator_swallows(func: nodes.FunctionDef) -> bool:
    """Return True if a decorator function swallows exceptions.

    Finds the returned wrapper function and checks its body.
    """
    wrapper = _find_returned_function(func)
    if wrapper is not None:
        return _check_body_shallow(wrapper.body) is not None
    return _check_body_shallow(func.body) is not None


def _find_returned_function(func: nodes.FunctionDef) -> nodes.FunctionDef | None:
    """Find the function returned by a decorator or decorator factory."""
    inner_funcs: dict[str, nodes.FunctionDef] = {}
    for child in func.body:
        if isinstance(child, nodes.FunctionDef):
            inner_funcs[child.name] = child

    if not inner_funcs:
        return None

    for child in func.body:
        if isinstance(child, nodes.Return) and isinstance(child.value, nodes.Name):
            if returned := inner_funcs.get(child.value.name):
                deeper = _find_returned_function(returned)
                return deeper if deeper is not None else returned

    if len(inner_funcs) == 1:
        inner = next(iter(inner_funcs.values()))
        deeper = _find_returned_function(inner)
        return deeper if deeper is not None else inner

    return None


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(SwallowedActionExceptionsChecker(linter))
