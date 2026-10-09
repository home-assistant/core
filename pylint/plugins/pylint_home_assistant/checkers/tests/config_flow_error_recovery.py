"""Checker for config flow error tests that do not finish the flow.

Only ``tests/components/<domain>/test_config_flow.py`` modules are checked.

A test that makes a flow step show an error, for example
``assert result["errors"] == {"base": "cannot_connect"}``, should then fix
the cause and finish the flow, to prove the user can recover from the error.
A test function is flagged when it asserts non-empty ``errors`` and, after
the last such assertion, never asserts that a result has type
``CREATE_ENTRY`` or aborted with a ``*_successful`` reason (as reauth and
reconfigure flows do). Helper functions from the integration's own tests
called after the error, such as ``_assert_create_entry(result)``, are
followed when astroid can infer them.
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module, parse_module

# How many levels of helper functions are followed to find the finished flow
_HELPER_DEPTH = 2


def _result_key(node: nodes.NodeNG) -> str | None:
    """Return ``key`` for ``result["key"]`` or ``result.get("key")``."""
    match node:
        case nodes.Subscript(slice=nodes.Const(value=str() as key)):
            return key
        case nodes.Call(
            func=nodes.Attribute(attrname="get"),
            args=[nodes.Const(value=str() as key), *_],
        ):
            return key
    return None


def _is_error_value(value: nodes.NodeNG) -> bool:
    """Return True if an expected ``errors`` value can hold an error."""
    match value:
        case nodes.Dict(items=items):
            return bool(items)
        case nodes.Const():
            return False
    return True


def _is_error_assert(node: nodes.Compare) -> bool:
    """Return True for ``result["errors"] == {"base": ...}`` and the like."""
    match node:
        case nodes.Compare(left=left, ops=[("==", value)]):
            if _result_key(left) == "errors":
                return _is_error_value(value)
            # result["errors"]["base"] == "cannot_connect"
            match left:
                case (
                    nodes.Subscript(value=errors)
                    | nodes.Call(func=nodes.Attribute(attrname="get", expr=errors))
                ):
                    return _result_key(errors) == "errors"
    return False


def _is_successful_reason(value: nodes.NodeNG) -> bool:
    """Return True if *value* is a ``*_successful`` abort reason.

    A test argument counts when every value it is parametrized with is one.
    """
    match value:
        case nodes.Const(value=str() as reason):
            return reason.endswith("_successful")
        case nodes.Name(name=name):
            func = value.scope()
            if not isinstance(func, nodes.FunctionDef) or name not in func.argnames():
                return False
            values = _parametrized_values(func, name)
            return bool(values) and all(
                isinstance(param, nodes.Const) and _is_successful_reason(param)
                for param in values
            )
    return False


def _parametrized_values(func: nodes.FunctionDef, name: str) -> list[nodes.NodeNG]:
    """Return the values *func* is parametrized with for argument *name*."""
    for decorator in func.decorators.nodes if func.decorators else ():
        match decorator:
            case nodes.Call(
                func=nodes.Attribute(attrname="parametrize"),
                args=[argnames, argvalues, *_],
            ):
                pass
            case _:
                continue
        match argnames:
            case nodes.Const(value=str() as names_str):
                names = [part.strip() for part in names_str.split(",")]
            case nodes.Tuple(elts=elts) | nodes.List(elts=elts):
                names = [elt.value for elt in elts if isinstance(elt, nodes.Const)]
            case _:
                continue
        if name not in names:
            continue
        index = names.index(name)
        if isinstance(argvalues, nodes.Name):
            try:
                argvalues = next(argvalues.infer(), None)
            except astroid.exceptions.AstroidError:
                return []
        if not isinstance(argvalues, nodes.Tuple | nodes.List):
            return []
        values = []
        for row in argvalues.elts:
            match row:
                case nodes.Call(func=nodes.Attribute(attrname="param"), args=args):
                    row_values = args
                case nodes.Tuple(elts=elts) if len(names) > 1:
                    row_values = elts
                case _:
                    row_values = [row]
            if len(row_values) != len(names):
                return []
            values.append(row_values[index])
        return values
    return []


def _is_finished_assert(node: nodes.Compare) -> bool:
    """Return True if *node* checks that the flow finished."""
    match node:
        case nodes.Compare(
            left=left,
            ops=[
                (
                    "is" | "==",
                    nodes.Attribute(attrname="CREATE_ENTRY")
                    | nodes.Const(value="create_entry"),
                )
            ],
        ):
            return _result_key(left) == "type"
        case nodes.Compare(left=left, ops=[("==", reason)]):
            return _result_key(left) == "reason" and _is_successful_reason(reason)
    return False


def _finishes_flow(
    node: nodes.NodeNG, package: str, depth: int = _HELPER_DEPTH
) -> bool:
    """Return True if *node* asserts, maybe through a helper, that a flow finished.

    Only helpers from the integration's own tests in *package* are followed.
    """
    match node:
        case nodes.Compare():
            return _is_finished_assert(node)
        # await assert_abort_flow(hass, flow_id, reason="reconfigure_successful")
        case nodes.Call(keywords=keywords) if any(
            keyword.arg == "reason" and _is_successful_reason(keyword.value)
            for keyword in keywords
        ):
            return True
        case nodes.Call() if depth:
            return any(
                isinstance(helper, nodes.FunctionDef)
                and (helper.root().name + ".").startswith(package + ".")
                and any(
                    _finishes_flow(child, package, depth - 1)
                    for child in helper.nodes_of_class((nodes.Compare, nodes.Call))
                )
                for helper in _infer_callee(node)
            )
    return False


def _infer_callee(node: nodes.Call) -> list[nodes.NodeNG]:
    """Return what the function called by *node* infers to."""
    try:
        return list(node.func.infer())
    except astroid.exceptions.AstroidError:
        return []


class ConfigFlowErrorRecovery(BaseChecker):
    """Checker for config flow error tests that do not finish the flow."""

    name = "home_assistant_tests_config_flow_error_recovery"
    priority = -1
    msgs = {
        "W7441": (
            (
                "Config flow test shows an error but never finishes the flow; "
                "fix the cause and assert the flow finishes"
            ),
            "home-assistant-tests-config-flow-error-recovery",
            (
                "Used when a config flow test asserts that a step shows an "
                "error, but does not check afterwards that the flow can still "
                "create the entry (or abort with a `*_successful` reason)."
            ),
        ),
    }
    options = ()

    _package: str | None = None

    def visit_module(self, node: nodes.Module) -> None:
        """Record the test package if the current module should be checked."""
        parsed = parse_module(node.name, include_test=True)
        self._package = None
        if (
            is_test_module(node.name)
            and parsed is not None
            and parsed.module == "test_config_flow"
        ):
            self._package = f"tests.components.{parsed.domain}"

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Flag tests that show an error without finishing the flow."""
        if (package := self._package) is None or not node.name.startswith("test_"):
            return
        errors = [
            compare
            for compare in node.nodes_of_class(nodes.Compare)
            if _is_error_assert(compare)
        ]
        if not errors:
            return
        last_error = max(errors, key=lambda compare: compare.lineno)
        if not any(
            child.lineno > last_error.lineno and _finishes_flow(child, package)
            for child in node.nodes_of_class((nodes.Compare, nodes.Call))
        ):
            self.add_message(
                "home-assistant-tests-config-flow-error-recovery", node=last_error
            )

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ConfigFlowErrorRecovery(linter))
