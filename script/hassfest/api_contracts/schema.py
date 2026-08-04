"""Render JSON schemas from API declarations without importing integrations."""

from __future__ import annotations

import ast
from typing import Any

from .common import SourceIndex, decorator_name, source_description

SCALAR_TYPES = {
    "str": "string",
    "bool": "boolean",
    "int": "integer",
    "float": "number",
}


def _resolved_expression(
    index: SourceIndex, module: str, node: ast.expr
) -> tuple[str, ast.expr]:
    """Follow assignment and import aliases to their source expression."""
    seen: set[tuple[str, str]] = set()
    while isinstance(node, (ast.Name, ast.Attribute)):
        key = (module, ast.dump(node, include_attributes=False))
        if key in seen or not (resolved := index.expression(module, node)):
            break
        seen.add(key)
        module, node = resolved
    return module, node


def schema_mapping(
    index: SourceIndex, module: str, node: ast.expr
) -> tuple[str, ast.Dict, bool] | None:
    """Find the explicit top-level mapping wrapped by a validator call."""
    module, node = _resolved_expression(index, module, node)
    match node:
        case ast.Dict():
            return module, node, False
        case ast.Call(args=arguments):
            for argument in arguments:
                if mapping := schema_mapping(index, module, argument):
                    mapping_module, mapping_node, allow_extra = mapping
                    if decorator_name(node) == "Schema":
                        allow_extra = any(
                            keyword.arg == "extra"
                            and decorator_name(keyword.value)
                            in {"ALLOW_EXTRA", "REMOVE_EXTRA"}
                            for keyword in node.keywords
                        )
                    return mapping_module, mapping_node, allow_extra
    return None


def _scalar_schema(node: ast.expr) -> dict[str, Any] | None:
    """Render a scalar name or literal."""
    match node:
        case ast.Name(id=name):
            type_name = name
        case ast.Constant(value=None):
            return {"type": "null"}
        case ast.Constant(value=value):
            if json_type := SCALAR_TYPES.get(type(value).__name__):
                return {"type": json_type, "const": value}
            return None
        case _:
            return None
    return (
        {"type": json_type}
        if (json_type := SCALAR_TYPES.get(type_name)) is not None
        else None
    )


def _primitive_schema(
    index: SourceIndex, module: str, node: ast.expr
) -> dict[str, Any]:
    """Render the source subset used by Voluptuous API validators."""
    module, node = _resolved_expression(index, module, node)
    if (
        (target := index.function_target(module, node))
        and (function := index.functions.get(target))
        and function.returns
    ):
        return annotation_schema(index, target[0], function.returns)
    if (scalar := _scalar_schema(node)) is not None:
        return scalar
    match node:
        case ast.Name(id="list") | ast.Name(id="set") | ast.Name(id="tuple"):
            return {"type": "array", "items": {}}
        case ast.Name(id="dict"):
            return {"type": "object"}
        case ast.Dict():
            return mapping_schema(index, module, node)
        case ast.List(elts=[]):
            return {"type": "array", "items": {}}
        case ast.List(elts=items) | ast.Tuple(elts=items):
            return {
                "type": "array",
                "items": (_primitive_schema(index, module, items[0]) if items else {}),
            }
        case ast.Call():
            return _validator_call_schema(index, module, node)
    return {}


def _validator_call_schema(
    index: SourceIndex, module: str, node: ast.Call
) -> dict[str, Any]:
    """Render explicit constraints from supported Voluptuous validators."""
    arguments = node.args
    match decorator_name(node):
        case "Schema" if arguments:
            if mapping := schema_mapping(index, module, node):
                return mapping_schema(index, *mapping)
            return _primitive_schema(index, module, arguments[0])
        case "Coerce" if arguments:
            return _primitive_schema(index, module, arguments[0])
        case "All" if arguments:
            return {
                key: value
                for argument in arguments
                for key, value in _primitive_schema(index, module, argument).items()
            }
        case "Range":
            values = {
                keyword.arg: index.value(module, keyword.value)
                for keyword in node.keywords
                if keyword.arg is not None
            }
            # Voluptuous accepts min, max, and their inclusivity flags positionally.
            for position, name in enumerate(
                ("min", "max", "min_included", "max_included")
            ):
                if position < len(arguments):
                    values[name] = index.value(module, arguments[position])
            result: dict[str, Any] = {}
            if values.get("min") is not None:
                result[
                    "exclusiveMinimum"
                    if values.get("min_included") is False
                    else "minimum"
                ] = values["min"]
            if values.get("max") is not None:
                result[
                    "exclusiveMaximum"
                    if values.get("max_included") is False
                    else "maximum"
                ] = values["max"]
            return result
        case "ExactSequence" if arguments and isinstance(
            arguments[0], (ast.List, ast.Tuple)
        ):
            items = [
                _primitive_schema(index, module, item) for item in arguments[0].elts
            ]
            return {
                "type": "array",
                "prefixItems": items,
                "items": False,
                "minItems": len(items),
                "maxItems": len(items),
            }
        case "In" if arguments:
            values = index.value(module, arguments[0])
            if values is not None:
                return {"enum": values if isinstance(values, list) else [values]}
        case "Any" if arguments:
            schemas = [
                _primitive_schema(index, module, argument) for argument in arguments
            ]
            return {} if any(not schema for schema in schemas) else {"anyOf": schemas}
    return {}


def mapping_key(
    index: SourceIndex, module: str, node: ast.expr
) -> tuple[str, bool] | None:
    """Return an explicit Voluptuous mapping key and requiredness."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, False

    if not isinstance(node, ast.Call) or not node.args:
        return None
    marker = decorator_name(node)

    if marker not in {"Required", "Optional"}:
        return None

    value = index.value(module, node.args[0])

    return (value, marker == "Required") if isinstance(value, str) else None


def mapping_schema(
    index: SourceIndex, module: str, node: ast.Dict, allow_extra: bool = False
) -> dict[str, Any]:
    """Render an explicitly declared Voluptuous mapping."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    additional_properties: dict[str, Any] | None = None
    for raw_key, value in zip(node.keys, node.values, strict=True):
        if raw_key is None:
            continue
        if not (key := mapping_key(index, module, raw_key)):
            key_schema = _primitive_schema(index, module, raw_key)
            if key_schema.get("type") == "string":
                additional_properties = _primitive_schema(index, module, value)
            continue
        name, is_required = key
        field_schema = _primitive_schema(index, module, value)
        description = next(
            (
                index.value(module, keyword.value)
                for keyword in (
                    raw_key.keywords if isinstance(raw_key, ast.Call) else []
                )
                if keyword.arg == "description"
            ),
            None,
        )
        field_schema["description"] = source_description(
            index,
            module,
            raw_key,
            description if isinstance(description, str) else "",
        )
        properties[name] = field_schema
        if is_required:
            required.append(name)
    return {
        "type": "object",
        **({"required": required} if required else {}),
        "properties": properties,
        "additionalProperties": (
            additional_properties if additional_properties is not None else allow_extra
        ),
    }


def annotation_schema(
    index: SourceIndex,
    module: str,
    node: ast.expr,
    seen: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Render an explicitly attached Python result type."""
    if (scalar := _scalar_schema(node)) is not None:
        return scalar
    match node:
        case ast.Name(id="None") | ast.Constant(value=None):
            return {"type": "null"}
        case ast.Name(id="Any"):
            return {}
        case ast.BinOp(left=left, op=ast.BitOr(), right=right):
            return {
                "anyOf": [
                    annotation_schema(index, module, left, seen),
                    annotation_schema(index, module, right, seen),
                ]
            }
        case ast.Subscript(value=value, slice=item):
            match decorator_name(value):
                case "tuple" if isinstance(item, ast.Tuple):
                    items = [
                        annotation_schema(index, module, element, seen)
                        for element in item.elts
                    ]
                    return {
                        "type": "array",
                        "prefixItems": items,
                        "items": False,
                        "minItems": len(items),
                        "maxItems": len(items),
                    }
                case "list" | "set" | "tuple" | "Sequence":
                    return {
                        "type": "array",
                        "items": annotation_schema(index, module, item, seen),
                    }
                case "dict" | "Mapping":
                    value_type = item.elts[1] if isinstance(item, ast.Tuple) else item
                    return {
                        "type": "object",
                        "additionalProperties": annotation_schema(
                            index, module, value_type, seen
                        ),
                    }
                case "NotRequired" | "Required":
                    return annotation_schema(index, module, item, seen)
                case "Literal":
                    values = item.elts if isinstance(item, ast.Tuple) else [item]
                    return {"enum": [index.value(module, value) for value in values]}

    if not (target := index.class_target(module, node)):
        return {}
    target_module, _ = target
    seen = set() if seen is None else seen
    if target in seen or not (class_node := index.classes.get(target)):
        return {}
    seen = seen | {target}

    if any(decorator_name(base) == "TypedDict" for base in class_node.bases):
        properties: dict[str, Any] = {}
        required: list[str] = []
        total = next(
            (
                index.value(target_module, keyword.value)
                for keyword in class_node.keywords
                if keyword.arg == "total"
            ),
            True,
        )

        for field in class_node.body:
            if not isinstance(field, ast.AnnAssign) or not isinstance(
                field.target, ast.Name
            ):
                # Skip non-annotated or non-name fields, which are not valid TypedDict members.
                continue

            properties[field.target.id] = annotation_schema(
                index, target_module, field.annotation, seen
            )
            properties[field.target.id]["description"] = source_description(
                index, target_module, field
            )
            marker = (
                decorator_name(field.annotation.value)
                if isinstance(field.annotation, ast.Subscript)
                else ""
            )

            # PEP 655 field markers override the TypedDict's class-level total.
            if marker == "Required" or (total is not False and marker != "NotRequired"):
                required.append(field.target.id)
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        schema["description"] = source_description(
            index, target_module, class_node, ast.get_docstring(class_node) or ""
        )
        return schema

    if any(decorator_name(item) == "dataclass" for item in class_node.decorator_list):
        fields = [
            (field.target.id, field.annotation, field)
            for field in class_node.body
            if isinstance(field, ast.AnnAssign) and isinstance(field.target, ast.Name)
        ]
        schema = {
            "type": "object",
            "properties": {
                name: {
                    **annotation_schema(index, target_module, annotation, seen),
                    "description": source_description(index, target_module, field),
                }
                for name, annotation, field in fields
            },
            "required": [name for name, _, field in fields if field.value is None],
        }
        schema["description"] = source_description(
            index, target_module, class_node, ast.get_docstring(class_node) or ""
        )
        return schema

    if any(decorator_name(base) in {"Enum", "StrEnum"} for base in class_node.bases):
        enum_values = [
            index.value(target_module, field.value)
            for field in class_node.body
            if isinstance(field, (ast.Assign, ast.AnnAssign))
            and field.value is not None
        ]
        if enum_values and all(isinstance(value, str) for value in enum_values):
            return {
                "type": "string",
                "enum": enum_values,
                "description": source_description(
                    index,
                    target_module,
                    class_node,
                    ast.get_docstring(class_node) or "",
                ),
            }

    # Unsupported source stays unconstrained; guessing would publish a false contract.
    return {}
