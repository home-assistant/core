"""Shared AST traversal utilities for pylint_home_assistant checkers."""

from collections.abc import Iterator

import astroid
from astroid import nodes


def safe_ancestors(class_node: nodes.ClassDef) -> list[nodes.ClassDef]:
    """Return ``class_node.ancestors()`` swallowing inference errors."""
    try:
        return list(class_node.ancestors())
    except astroid.exceptions.InferenceError:
        return []


def subscript_base_classes(class_node: nodes.ClassDef) -> Iterator[nodes.ClassDef]:
    """Yield ClassDefs from subscript bases (e.g. ``class B(Base[T])``).

    astroid's ``ancestors()`` drops Subscript bases such as
    ``VeSyncBaseEntity[VeSyncFanBase | VeSyncPurifier]`` (PEP-695 generic
    syntax), so this method recovers them by inferring the subscript's
    value.
    """
    for base in class_node.bases:
        if not isinstance(base, nodes.Subscript):
            continue
        try:
            inferred = list(base.value.infer())
        except astroid.exceptions.InferenceError:
            continue
        for inferred_node in inferred:
            if isinstance(inferred_node, nodes.ClassDef):
                yield inferred_node


def extended_ancestors(class_node: nodes.ClassDef) -> Iterator[nodes.ClassDef]:
    """Yield all ancestors including transitive subscript-based ones."""
    seen: set[str] = set()
    stack: list[nodes.ClassDef] = [class_node]

    while stack:
        current = stack.pop()
        for ancestor in safe_ancestors(current):
            qname = ancestor.qname()
            if qname in seen:
                continue
            seen.add(qname)
            yield ancestor
            stack.append(ancestor)
        for subscript_base in subscript_base_classes(current):
            qname = subscript_base.qname()
            if qname in seen:
                continue
            seen.add(qname)
            yield subscript_base
            stack.append(subscript_base)


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
