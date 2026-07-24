"""Checker enforcing a typed ConfigEntry alias for ``runtime_data`` usage.

When code accesses ``entry.runtime_data`` the corresponding parameter should
be annotated with a subscripted ``ConfigEntry`` alias (e.g. ``type
MyConfigEntry = ConfigEntry[MyRuntimeData]``) rather than the bare
``ConfigEntry`` class. The typed alias propagates the runtime_data type to
mypy throughout the integration.

Only checked in the integration's ``__init__.py`` for now, which is where
``runtime_data`` is typically assigned.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import parse_module


class HassEnforceRuntimeDataTypeChecker(BaseChecker):
    """Checker for typed ConfigEntry alias when using runtime_data."""

    name = "home_assistant_enforce_runtime_data_type"
    priority = -1
    msgs = {
        "W7423": (
            "Parameter '%s' accesses runtime_data but is annotated with bare "
            "'ConfigEntry'. Use a typed alias like "
            "'type MyConfigEntry = ConfigEntry[MyRuntimeData]' so mypy knows "
            "the runtime_data type "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/runtime-data)",
            "home-assistant-runtime-data-needs-typed-config-entry",
            "Used when a parameter annotated as the bare 'ConfigEntry' class "
            "is used with '.runtime_data'. Define a subscripted alias such as "
            "'type MyConfigEntry = ConfigEntry[MyRuntimeData]' and annotate "
            "the parameter with it so the type of 'runtime_data' is known.",
        ),
    }
    options = ()

    def visit_attribute(self, node: nodes.Attribute) -> None:
        """Check ``<name>.runtime_data`` read accesses."""
        self._check(node)

    def visit_assignattr(self, node: nodes.AssignAttr) -> None:
        """Check ``<name>.runtime_data = ...`` assignments."""
        self._check(node)

    def visit_delattr(self, node: nodes.DelAttr) -> None:
        """Check ``del <name>.runtime_data`` deletions."""
        self._check(node)

    def _check(self, node: nodes.Attribute | nodes.AssignAttr | nodes.DelAttr) -> None:
        if node.attrname != "runtime_data":
            return

        # Only flag in integration's __init__.py for now.
        parsed = parse_module(node.root().name)
        if parsed is None or parsed.module is not None:
            return

        # The expression we read runtime_data from must be a simple name.
        if not isinstance(node.expr, nodes.Name):
            return
        param_name = node.expr.name

        func = _enclosing_function(node)
        if func is None:
            return

        annotation = _get_argument_annotation(func, param_name)
        if annotation is None:
            return

        if _is_bare_config_entry(annotation):
            self.add_message(
                "home-assistant-runtime-data-needs-typed-config-entry",
                node=node,
                args=(param_name,),
            )


def _enclosing_function(
    node: nodes.NodeNG,
) -> nodes.FunctionDef | nodes.AsyncFunctionDef | None:
    """Walk up to find the enclosing (possibly async) function."""
    current = node.parent
    while current is not None:
        if isinstance(current, (nodes.FunctionDef, nodes.AsyncFunctionDef)):
            return current
        current = current.parent
    return None


def _get_argument_annotation(
    func: nodes.FunctionDef | nodes.AsyncFunctionDef, name: str
) -> nodes.NodeNG | None:
    """Return the annotation node for argument *name* in *func*, if any."""
    args = func.args
    # Combine positional/keyword-only argument lists with their annotations.
    arg_lists = (
        (args.args or [], args.annotations or []),
        (args.kwonlyargs or [], args.kwonlyargs_annotations or []),
        (args.posonlyargs or [], args.posonlyargs_annotations or []),
    )
    for arg_nodes, annotation_nodes in arg_lists:
        for arg, annotation in zip(arg_nodes, annotation_nodes, strict=False):
            if arg.name == name:
                return annotation
    return None


def _is_bare_config_entry(annotation: nodes.NodeNG) -> bool:
    """Return True if *annotation* refers to the bare ``ConfigEntry`` class.

    Subscripted forms like ``ConfigEntry[Foo]`` or aliases like
    ``MyConfigEntry`` are not flagged.
    """
    match annotation:
        case nodes.Name(name="ConfigEntry"):
            return True
        case nodes.Attribute(attrname="ConfigEntry"):
            return True
    return False


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceRuntimeDataTypeChecker(linter))
