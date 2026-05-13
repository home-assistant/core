"""Shared AST traversal utilities for pylint_home_assistant checkers."""

from astroid import nodes


def enclosing_function(node: nodes.NodeNG) -> nodes.FunctionDef | None:
    """Walk up the tree to find the enclosing function."""
    current = node.parent
    while current is not None:
        if isinstance(current, nodes.FunctionDef):
            return current
        current = current.parent
    return None


def get_schema_field_name(node: nodes.Call) -> str | None:
    """Extract the field name from ``vol.Required(...)`` or ``vol.Optional(...)``.

    Returns the string field name (either a literal or a ``Name`` identifier),
    or ``None`` if *node* is not a voluptuous schema field call.
    """
    match node:
        case nodes.Call(
            func=nodes.Attribute(attrname="Required" | "Optional"),
            args=[nodes.Name(name=val) | nodes.Const(value=str(val)), *_],
        ):
            return str(val)
    return None


def is_in_subentry_flow(node: nodes.NodeNG) -> bool:
    """Return True if *node* is inside a ``ConfigSubentryFlow`` class."""
    current = node.parent
    while current is not None:
        if isinstance(current, nodes.ClassDef):
            for base in current.bases:
                match base:
                    case nodes.Name(name=name) if "SubentryFlow" in name:
                        return True
                    case nodes.Attribute(attrname=attrname) if (
                        "SubentryFlow" in attrname
                    ):
                        return True
        current = current.parent
    return False
