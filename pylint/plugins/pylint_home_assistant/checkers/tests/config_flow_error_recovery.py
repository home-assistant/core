"""Checker for config flow error tests that do not finish the flow.

Only ``tests/components/<domain>/test_config_flow.py`` modules are checked.

A test that makes a flow step show an error, for example
``assert result["errors"] == {"base": "cannot_connect"}``, should then fix
the cause and finish the flow, to prove the user can recover from the error.
Any error counts, on any field: ``errors == {...}``, ``errors["base"] == ...``,
``"base" in errors``, a bare ``assert result["errors"]`` and
``errors != {}``. A test function is flagged when it asserts an error and,
after the last such assertion, never asserts that a result has type
``CREATE_ENTRY`` or aborted with a ``*_successful`` reason (as reauth and
reconfigure flows do). A finishing assertion in a branch that cannot run
after the error, such as the ``else`` of the ``if`` that shows the error,
does not count. Helper functions from the integration's own tests, such as
``assert_form_error(result)`` or ``_assert_create_entry(result)``, are
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


def _is_no_errors_value(value: nodes.NodeNG) -> bool:
    """Return True for ``{}`` and ``None``."""
    match value:
        case nodes.Dict(items=[]) | nodes.Const(value=None):
            return True
    return False


def _assert_parts(test: nodes.NodeNG) -> list[nodes.NodeNG]:
    """Return the conditions of ``assert a and b``, or the test itself."""
    if isinstance(test, nodes.BoolOp) and test.op == "and":
        return list(test.values)
    return [test]


def _is_error_assert(
    node: nodes.NodeNG, arguments: dict[str, nodes.NodeNG] | None = None
) -> bool:
    """Return True if the asserted *node* expects the step to show an error.

    *arguments* maps a helper's parameters to the values it was called with.
    """
    # assert result["errors"]
    if _result_key(node) == "errors":
        return True
    match node:
        case nodes.Compare(left=left, ops=[("==", value)]):
            if _result_key(left) == "errors":
                if isinstance(value, nodes.Name) and arguments:
                    value = arguments.get(value.name, value)
                return _is_error_value(value)
            # result["errors"]["base"] == "cannot_connect"
            match left:
                case (
                    nodes.Subscript(value=errors)
                    | nodes.Call(func=nodes.Attribute(attrname="get", expr=errors))
                ):
                    return _result_key(errors) == "errors"
        # assert "base" in result["errors"]
        case nodes.Compare(ops=[("in", errors)]):
            return _result_key(errors) == "errors"
        # assert result["errors"] != {}
        case nodes.Compare(left=left, ops=[("!=" | "is not", value)]):
            return _result_key(left) == "errors" and _is_no_errors_value(value)
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


def _is_finished_assert(
    node: nodes.Compare, arguments: dict[str, nodes.NodeNG] | None = None
) -> bool:
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
            if isinstance(reason, nodes.Name) and arguments:
                reason = arguments.get(reason.name, reason)
            return _result_key(left) == "reason" and _is_successful_reason(reason)
    return False


def _finishes_flow(
    node: nodes.NodeNG,
    package: str,
    depth: int = _HELPER_DEPTH,
    arguments: dict[str, nodes.NodeNG] | None = None,
) -> bool:
    """Return True if *node* asserts, maybe through a helper, that a flow finished.

    Only helpers from the integration's own tests in *package* are followed.
    *arguments* holds the values the helper containing *node* was called with.
    """
    match node:
        case nodes.Compare():
            return _is_finished_assert(node, arguments)
        # await assert_abort_flow(hass, flow_id, reason="reconfigure_successful")
        case nodes.Call(keywords=keywords) if any(
            keyword.arg == "reason" and _is_successful_reason(keyword.value)
            for keyword in keywords
        ):
            return True
        case nodes.Call() if depth:
            return any(
                _finishes_flow(
                    child, package, depth - 1, _call_arguments(node, helper, arguments)
                )
                for helper in _own_helpers(node, package)
                for child in helper.nodes_of_class((nodes.Compare, nodes.Call))
            )
    return False


def _own_helpers(node: nodes.Call, package: str) -> list[nodes.FunctionDef]:
    """Return the functions from the tests in *package* that *node* calls."""
    try:
        inferred = list(node.func.infer())
    except astroid.exceptions.AstroidError:
        return []
    return [
        helper
        for helper in inferred
        if isinstance(helper, nodes.FunctionDef)
        and (helper.root().name + ".").startswith(package + ".")
    ]


def _branch(node: nodes.NodeNG, branch_node: nodes.If | nodes.Match) -> int | None:
    """Return the index of the branch of *branch_node* that contains *node*."""
    child = node
    while child.parent is not branch_node:
        child = child.parent
    branches = (
        [[case] for case in branch_node.cases]
        if isinstance(branch_node, nodes.Match)
        else [branch_node.body, branch_node.orelse]
    )
    return next(
        (index for index, branch in enumerate(branches) if child in branch), None
    )


def _in_exclusive_branches(first: nodes.NodeNG, second: nodes.NodeNG) -> bool:
    """Return True if *first* and *second* are in branches that never both run."""
    second_ancestors = set(second.node_ancestors())
    common = next(
        (
            ancestor
            for ancestor in first.node_ancestors()
            if ancestor in second_ancestors
        ),
        None,
    )
    if not isinstance(common, nodes.If | nodes.Match):
        return False
    first_branch = _branch(first, common)
    second_branch = _branch(second, common)
    return None not in (first_branch, second_branch) and first_branch != second_branch


def _call_arguments(
    call: nodes.Call,
    helper: nodes.FunctionDef,
    arguments: dict[str, nodes.NodeNG] | None,
) -> dict[str, nodes.NodeNG]:
    """Map the parameters of *helper* to the values *call* passes.

    Values that are parameters of the calling helper resolve to *arguments*.
    """
    params = [*helper.args.posonlyargs, *helper.args.args]
    bound: dict[str, nodes.NodeNG] = {}
    for param, default in zip(
        params[len(params) - len(helper.args.defaults) :],
        helper.args.defaults,
        strict=True,
    ):
        bound[param.name] = default
    for param, default in zip(
        helper.args.kwonlyargs, helper.args.kw_defaults, strict=True
    ):
        if default is not None:
            bound[param.name] = default
    for param, value in zip(params, call.args, strict=False):
        if isinstance(value, nodes.Starred):
            break
        bound[param.name] = value
    for keyword in call.keywords:
        if keyword.arg is not None:
            bound[keyword.arg] = keyword.value
    if arguments:
        bound = {
            name: arguments.get(value.name, value)
            if isinstance(value, nodes.Name)
            else value
            for name, value in bound.items()
        }
    return bound


def _unrecovered_error(
    scope: nodes.FunctionDef,
    package: str,
    depth: int = _HELPER_DEPTH,
    arguments: dict[str, nodes.NodeNG] | None = None,
) -> nodes.NodeNG | None:
    """Return the last error shown in *scope* if the flow is not finished after it.

    Errors shown by helpers from the tests in *package* count as well, unless
    the helper finishes the flow itself. *arguments* holds the values a helper
    *scope* was called with.
    """
    errors = [
        test
        for assert_node in scope.nodes_of_class(nodes.Assert)
        for test in _assert_parts(assert_node.test)
        if _is_error_assert(test, arguments)
    ]
    if depth:
        errors.extend(
            call
            for call in scope.nodes_of_class(nodes.Call)
            if any(
                _unrecovered_error(
                    helper,
                    package,
                    depth - 1,
                    _call_arguments(call, helper, arguments),
                )
                is not None
                for helper in _own_helpers(call, package)
            )
        )
    if not errors:
        return None
    last_error = max(errors, key=lambda error: error.lineno)
    if any(
        child.lineno > last_error.lineno
        and not _in_exclusive_branches(last_error, child)
        and _finishes_flow(child, package, arguments=arguments)
        for child in scope.nodes_of_class((nodes.Compare, nodes.Call))
    ):
        return None
    return last_error


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
        if (last_error := _unrecovered_error(node, package)) is not None:
            self.add_message(
                "home-assistant-tests-config-flow-error-recovery", node=last_error
            )

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ConfigFlowErrorRecovery(linter))
