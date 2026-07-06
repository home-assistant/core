"""Type hint validation logic."""

import re
from typing import TYPE_CHECKING

from astroid import nodes
from astroid.exceptions import NameInferenceError

from .models import TypeHintMatch, _Special

if TYPE_CHECKING:
    from astroid.typing import InferenceResult

_KNOWN_GENERIC_TYPES: set[str] = {
    "ConfigEntry",
}
_KNOWN_GENERIC_TYPES_TUPLE = tuple(_KNOWN_GENERIC_TYPES)

_INNER_MATCH = r"((?:[\w\| ]+)|(?:\.{3})|(?:\w+\[.+\])|(?:\[\]))"
_TYPE_HINT_MATCHERS: dict[str, re.Pattern[str]] = {
    # a_or_b matches items such as "DiscoveryInfoType | None"
    # or "dict | list | None"
    "a_or_b": re.compile(rf"^(.+) \| {_INNER_MATCH}$"),
}
_INNER_MATCH_POSSIBILITIES = [i + 1 for i in range(5)]
_TYPE_HINT_MATCHERS.update(
    {
        f"x_of_y_{i}": re.compile(
            rf"^([\w\.]+)\[{_INNER_MATCH}" + f", {_INNER_MATCH}" * (i - 1) + r"\]$"
        )
        for i in _INNER_MATCH_POSSIBILITIES
    }
)


def is_valid_type(
    expected_type: list[str] | str | None | object,
    node: nodes.NodeNG,
    in_return: bool = False,
) -> bool:
    """Check the argument node against the expected type."""
    if expected_type is _Special.UNDEFINED:
        return True

    if isinstance(expected_type, list):
        for expected_type_item in expected_type:
            if is_valid_type(expected_type_item, node, in_return):
                return True
        return False

    # Const occurs when the type is None
    if expected_type is None or expected_type == "None":
        return isinstance(node, nodes.Const) and node.value is None

    assert isinstance(expected_type, str)

    # Const occurs when the type is an Ellipsis
    if expected_type == "...":
        return isinstance(node, nodes.Const) and node.value == Ellipsis

    # Special case for an empty list, such as Callable[[], TestServer]
    if expected_type == "[]":
        return isinstance(node, nodes.List) and not node.elts

    # Special case for `xxx | yyy`
    if match := _TYPE_HINT_MATCHERS["a_or_b"].match(expected_type):
        return (
            isinstance(node, nodes.BinOp)
            and is_valid_type(match.group(1), node.left)
            and is_valid_type(match.group(2), node.right)
        )

    # Special case for `xxx[aaa, bbb, ccc, ...]
    if (
        isinstance(node, nodes.Subscript)
        and isinstance(node.slice, nodes.Tuple)
        and (
            match := _TYPE_HINT_MATCHERS[f"x_of_y_{len(node.slice.elts)}"].match(
                expected_type
            )
        )
    ):
        # This special case is separate because we want Mapping[str, Any]
        # to also match dict[str, int] and similar
        if (
            len(node.slice.elts) == 2
            and in_return
            and match.group(1) == "Mapping"
            and match.group(3) == "Any"
        ):
            return (
                isinstance(node.value, nodes.Name)
                # We accept dict when Mapping is needed
                and node.value.name in ("Mapping", "dict")
                and isinstance(node.slice, nodes.Tuple)
                and is_valid_type(match.group(2), node.slice.elts[0])
                # Ignore second item
                # and is_valid_type(match.group(3), node.slice.elts[1])
            )

        # This is the default case
        return (
            is_valid_type(match.group(1), node.value)
            and isinstance(node.slice, nodes.Tuple)
            and all(
                is_valid_type(match.group(n + 2), node.slice.elts[n], in_return)
                for n in range(len(node.slice.elts))
            )
        )

    # Special case for xxx[yyy]
    if match := _TYPE_HINT_MATCHERS["x_of_y_1"].match(expected_type):
        return (
            isinstance(node, nodes.Subscript)
            and is_valid_type(match.group(1), node.value)
            and is_valid_type(match.group(2), node.slice)
        )

    # Special case for float in return type
    if (
        expected_type == "float"
        and in_return
        and isinstance(node, nodes.Name)
        and node.name in ("float", "int")
    ):
        return True

    # Special case for int in argument type
    if (
        expected_type == "int"
        and not in_return
        and isinstance(node, nodes.Name)
        and node.name in ("float", "int")
    ):
        return True

    # Allow subscripts or type aliases for generic types
    if (
        isinstance(node, nodes.Subscript)
        and isinstance(node.value, nodes.Name)
        and node.value.name in _KNOWN_GENERIC_TYPES
    ) or (
        isinstance(node, nodes.Name) and node.name.endswith(_KNOWN_GENERIC_TYPES_TUPLE)
    ):
        return True

    # Name occurs when a namespace is not used, eg. "HomeAssistant"
    if isinstance(node, nodes.Name) and node.name == expected_type:
        return True

    # Attribute occurs when a namespace is used, eg. "core.HomeAssistant"
    return isinstance(node, nodes.Attribute) and (
        node.attrname == expected_type or node.as_string() == expected_type
    )


def is_valid_return_type(match: TypeHintMatch, node: nodes.NodeNG) -> bool:
    """Check the return type annotation against the expected type."""
    if is_valid_type(match.return_type, node, True):
        return True

    if isinstance(node, nodes.BinOp):
        return is_valid_return_type(match, node.left) and is_valid_return_type(
            match, node.right
        )

    if isinstance(match.return_type, (str, list)) and isinstance(node, nodes.Name):
        if isinstance(match.return_type, str):
            valid_types = {match.return_type}
        else:
            valid_types = {el for el in match.return_type if isinstance(el, str)}
        if "Mapping[str, Any]" in valid_types:
            valid_types.add("TypedDict")

        try:
            for infer_node in node.infer():
                if _check_ancestry(infer_node, valid_types):
                    return True
        except NameInferenceError:
            for class_node in node.root().nodes_of_class(nodes.ClassDef):
                if class_node.name != node.name:
                    continue
                for infer_node in class_node.infer():
                    if _check_ancestry(infer_node, valid_types):
                        return True

    return False


def _check_ancestry(infer_node: InferenceResult, valid_types: set[str]) -> bool:
    if isinstance(infer_node, nodes.ClassDef):
        if infer_node.name in valid_types:
            return True
        for ancestor in infer_node.ancestors():
            if ancestor.name in valid_types:
                return True
    return False


def get_all_annotations(node: nodes.FunctionDef) -> list[nodes.NodeNG | None]:
    """Return all annotations for a function's arguments."""
    args = node.args
    annotations: list[nodes.NodeNG | None] = (
        args.posonlyargs_annotations + args.annotations + args.kwonlyargs_annotations
    )
    if args.vararg is not None:
        annotations.append(args.varargannotation)
    if args.kwarg is not None:
        annotations.append(args.kwargannotation)
    return annotations


def get_named_annotation(
    node: nodes.FunctionDef, key: str
) -> tuple[nodes.NodeNG, nodes.NodeNG] | tuple[None, None]:
    """Return (arg_node, annotation) for the argument named *key*."""
    args = node.args
    for index, arg_node in enumerate(args.args):
        if key == arg_node.name:
            return arg_node, args.annotations[index]

    for index, arg_node in enumerate(args.kwonlyargs):
        if key == arg_node.name:
            return arg_node, args.kwonlyargs_annotations[index]

    return None, None


def has_valid_annotations(
    annotations: list[nodes.NodeNG | None],
) -> bool:
    """Return True if at least one annotation is not None."""
    return any(annotation is not None for annotation in annotations)
