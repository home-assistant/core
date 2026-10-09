"""Checker for config flow tests that do not assert the entry's unique ID.

Only ``tests/components/<domain>/test_config_flow.py`` modules are checked,
and only when the integration's config flow calls ``async_set_unique_id``.

A happy path config flow test should check the unique ID of the entry it
creates, for example with ``assert result["result"].unique_id == "1234"``.
A test function is flagged when it asserts that a flow result has type
``CREATE_ENTRY`` and none of its asserts references ``unique_id`` or a
``snapshot``.

Results of ``hass.config_entries.options`` and ``subentries`` flows are
ignored, as those don't set a unique ID; results that can't be traced, such
as those returned by a helper, are checked. Tests that start an options or
subentry flow are skipped, as they run the config flow only as setup. Tests
that recover from an error are skipped too: they make a mock raise through
``side_effect`` or expect non-empty ``errors``.
"""

from pathlib import Path

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.integration import get_tested_integration_dir
from pylint_home_assistant.helpers.module_info import is_test_module, parse_module

_OTHER_FLOW_MANAGERS = frozenset({"options", "subentries"})


def _calls_set_unique_id(source: Path) -> bool:
    """Return True if *source* calls ``async_set_unique_id``."""
    try:
        module = astroid.parse(source.read_text())
    except astroid.exceptions.AstroidSyntaxError:
        return False
    for call in module.nodes_of_class(nodes.Call):
        match call.func:
            case (
                nodes.Attribute(attrname="async_set_unique_id")
                | nodes.Name(name="async_set_unique_id")
            ):
                return True
    return False


def _config_flow_sets_unique_id(integration_dir: Path) -> bool:
    """Return True if the integration's config flow sets a unique ID."""
    sources = [
        integration_dir / "config_flow.py",
        *(integration_dir / "config_flow").glob("*.py"),
    ]
    return any(source.is_file() and _calls_set_unique_id(source) for source in sources)


def _create_entry_result_name(node: nodes.Compare) -> str | None:
    """Return ``result`` for ``result["type"] is FlowResultType.CREATE_ENTRY``.

    ``result.get("type")`` is matched as well.
    """
    match node:
        case nodes.Compare(
            left=nodes.Subscript(
                value=nodes.Name() as result, slice=nodes.Const(value="type")
            )
            | nodes.Call(
                func=nodes.Attribute(attrname="get", expr=nodes.Name() as result),
                args=[nodes.Const(value="type")],
            ),
            ops=[
                (
                    "is" | "==",
                    nodes.Attribute(attrname="CREATE_ENTRY")
                    | nodes.Const(value="create_entry"),
                )
            ],
        ):
            name: str = result.name
            return name
    return None


def _is_other_flow_result(value: nodes.NodeNG | None) -> bool:
    """Return True for ``await hass.config_entries.options.async_configure(...)``.

    Results that can't be traced, such as those of a helper, could come from
    a config flow, so only options and subentry flow results are excluded.
    """
    match value:
        case nodes.Await(
            value=nodes.Call(
                func=nodes.Attribute(expr=nodes.Attribute(attrname=manager))
            )
        ):
            return manager in _OTHER_FLOW_MANAGERS
    return False


def _starts_other_flow(func: nodes.FunctionDef) -> bool:
    """Return True if the test starts an options or subentry flow.

    Such a test runs the config flow only to set up the entry it needs.
    """
    for call in func.nodes_of_class(nodes.Call):
        match call.func:
            case nodes.Attribute(
                attrname="async_init", expr=nodes.Attribute(attrname=manager)
            ) if manager in _OTHER_FLOW_MANAGERS:
                return True
    return False


def _last_assigned_value(
    func: nodes.FunctionDef, name: str, before: nodes.NodeNG
) -> nodes.NodeNG | None:
    """Return the value last assigned to *name* in *func* before *before*."""
    value: nodes.NodeNG | None = None
    for assign in func.nodes_of_class(nodes.Assign):
        if assign.lineno < before.lineno and any(
            isinstance(target, nodes.AssignName) and target.name == name
            for target in assign.targets
        ):
            value = assign.value
    return value


def _is_errors(node: nodes.NodeNG) -> bool:
    """Return True for ``result["errors"]`` or ``result.get("errors")``."""
    match node:
        case (
            nodes.Subscript(slice=nodes.Const(value="errors"))
            | nodes.Call(
                func=nodes.Attribute(attrname="get"),
                args=[nodes.Const(value="errors"), *_],
            )
        ):
            return True
    return False


def _is_errors_item(node: nodes.NodeNG) -> bool:
    """Return True for ``result["errors"]["base"]`` or its ``.get()`` forms."""
    match node:
        case (
            nodes.Subscript(value=inner)
            | nodes.Call(func=nodes.Attribute(attrname="get", expr=inner))
        ) if _is_errors(inner):
            return True
    return False


def _is_error_value(value: nodes.NodeNG) -> bool:
    """Return True if an expected ``errors`` value can hold an error."""
    match value:
        case nodes.Dict(items=items):
            return bool(items)
        case nodes.Const():
            return False
    return True


def _expects_error(left: nodes.NodeNG, value: nodes.NodeNG) -> bool:
    """Return True if ``left == value`` expects the flow to show an error."""
    if _is_errors(left):
        return _is_error_value(value)
    return _is_errors_item(left) and not (
        isinstance(value, nodes.Const) and value.value is None
    )


def _is_exception(value: nodes.NodeNG) -> bool:
    """Return True if *value* is an exception class or instance."""
    return isinstance(
        value, (nodes.ClassDef, astroid.Instance)
    ) and value.is_subtype_of("builtins.BaseException")


def _is_injected_error(value: nodes.NodeNG) -> bool:
    """Return True if a ``side_effect`` value can raise an error.

    Resetting it to ``None``, replacing a method with a function or mock, or
    returning a sequence of values does not. Values that can't be inferred,
    such as a parametrized ``exception``, are assumed to raise.
    """
    match value:
        case nodes.Const(value=None) | nodes.Lambda():
            return False
        case nodes.List(elts=elts) | nodes.Tuple(elts=elts):
            return any(_is_injected_error(elt) for elt in elts)
        case nodes.Call(func=func):
            value = func

    try:
        inferred = list(value.infer())
    except astroid.exceptions.AstroidError:
        return True

    return any(item is astroid.Uninferable or _is_exception(item) for item in inferred)


def _recovers_from_error(func: nodes.FunctionDef) -> bool:
    """Return True if the test injects an error or expects one."""
    for node in func.nodes_of_class((nodes.AssignAttr, nodes.Keyword, nodes.Compare)):
        match node:
            case (
                nodes.AssignAttr(
                    attrname="side_effect", parent=nodes.Assign(value=value)
                )
                | nodes.Keyword(arg="side_effect", value=value)
            ) if _is_injected_error(value):
                return True
            case nodes.Compare(left=left, ops=[("==", value)]) if _expects_error(
                left, value
            ):
                return True
    return False


def _checks_unique_id(func: nodes.FunctionDef) -> bool:
    """Return True if an assert in the test checks a unique ID or a snapshot."""
    for assert_node in func.nodes_of_class(nodes.Assert):
        for node in assert_node.nodes_of_class(
            (nodes.Attribute, nodes.Const, nodes.Name)
        ):
            match node:
                case (
                    nodes.Attribute(attrname="unique_id")
                    | nodes.Const(value="unique_id")
                    | nodes.Name(name="snapshot")
                ):
                    return True
    return False


class ConfigFlowUniqueId(BaseChecker):
    """Checker for config flow tests that do not assert the unique ID."""

    name = "home_assistant_tests_config_flow_unique_id"
    priority = -1
    msgs = {
        "W7440": (
            (
                "Config flow test creates an entry without asserting its unique "
                'ID, add for example `assert result["result"].unique_id == ...`'
            ),
            "home-assistant-tests-config-flow-unique-id",
            (
                "Used when a happy path config flow test asserts that an entry "
                "was created but never checks its unique ID."
            ),
        ),
    }
    options = ()

    _check_module: bool = False

    def visit_module(self, node: nodes.Module) -> None:
        """Record whether the current module's tests should be checked."""
        parsed = parse_module(node.name, include_test=True)
        self._check_module = (
            is_test_module(node.name)
            and parsed is not None
            and parsed.module == "test_config_flow"
            and (integration_dir := get_tested_integration_dir(node)) is not None
            and _config_flow_sets_unique_id(integration_dir)
        )

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Flag happy path tests that create an entry but skip the unique ID."""
        if (
            not self._check_module
            or not node.name.startswith("test_")
            or _starts_other_flow(node)
        ):
            return
        for compare in node.nodes_of_class(nodes.Compare):
            if (name := _create_entry_result_name(compare)) is None:
                continue
            if _is_other_flow_result(_last_assigned_value(node, name, compare)):
                continue
            if not _recovers_from_error(node) and not _checks_unique_id(node):
                self.add_message(
                    "home-assistant-tests-config-flow-unique-id", node=compare
                )
            return

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ConfigFlowUniqueId(linter))
