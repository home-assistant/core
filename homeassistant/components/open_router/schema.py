"""Convert output schemas for OpenRouter's strict structured output format."""
# Documentation: https://openrouter.ai/docs/guides/features/structured-outputs

from collections.abc import Iterator
from copy import deepcopy
from typing import Any
from urllib.parse import unquote

from homeassistant.exceptions import HomeAssistantError

_SCHEMA_MAPS = (
    "properties",
    "$defs",
    "definitions",
    "patternProperties",
    "dependentSchemas",
)
_SCHEMA_LISTS = ("anyOf", "oneOf", "allOf", "prefixItems")
_SCHEMA_VALUES = (
    "items",
    "contains",
    "additionalProperties",
    "propertyNames",
    "not",
    "if",
    "then",
    "else",
)


def adjust_schema(schema: dict[str, Any] | bool) -> None:
    """Normalize known incompatibilities, preserving unfamiliar API features."""
    if isinstance(schema, dict):
        _stabilize_references(schema)
    _adjust_schema(schema)


def _walk_schemas(schema: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Walk schema locations without interpreting examples or literal data as schemas."""
    yield schema
    for keyword in _SCHEMA_MAPS:
        for child in schema.get(keyword, {}).values():
            if isinstance(child, dict):
                yield from _walk_schemas(child)
    for keyword in _SCHEMA_LISTS:
        for child in schema.get(keyword, []):
            if isinstance(child, dict):
                yield from _walk_schemas(child)
    for keyword in _SCHEMA_VALUES:
        if isinstance(child := schema.get(keyword), dict):
            yield from _walk_schemas(child)


def _stabilize_references(schema: dict[str, Any]) -> None:
    """Move reference targets to root definitions before their paths can change."""
    references = {node["$ref"] for node in _walk_schemas(schema) if "$ref" in node}
    replacements: dict[str, str] = {}
    definitions: dict[str, Any] = {}
    existing_names = set(schema.get("$defs", {}))
    for reference in sorted(references):
        target = _resolve_reference(reference, schema)
        parts = _reference_parts(reference)
        if not parts or (len(parts) == 2 and parts[0] == "$defs"):
            replacements[reference] = reference
            continue
        name = f"_ha_ref_{len(definitions)}"
        while name in existing_names:
            name = f"_{name}"
        existing_names.add(name)
        definitions[name] = deepcopy(target)
        replacements[reference] = f"#/$defs/{name}"

    if definitions:
        schema.setdefault("$defs", {}).update(definitions)
    for node in _walk_schemas(schema):
        if "$ref" in node:
            node["$ref"] = replacements[node["$ref"]]


def _reference_parts(reference: str) -> list[str]:
    """Decode a local JSON Pointer, including URI fragment escaping."""
    if reference == "#":
        return []
    if not reference.startswith("#/"):
        raise HomeAssistantError(
            f"Unsupported OpenRouter output schema reference: {reference}"
        )
    return [
        part.replace("~1", "/").replace("~0", "~")
        for part in unquote(reference[2:]).split("/")
    ]


def _resolve_reference(reference: str, root: dict[str, Any]) -> dict[str, Any] | bool:
    """Resolve local references through both objects and arrays."""
    target: Any = root
    try:
        for part in _reference_parts(reference):
            if isinstance(target, list):
                target = target[_array_index(part)]
            else:
                target = target[part]
    except (KeyError, IndexError, TypeError, ValueError) as err:
        raise HomeAssistantError(
            f"Invalid OpenRouter output schema reference: {reference}"
        ) from err
    if not isinstance(target, (dict, bool)):
        raise HomeAssistantError(
            f"Unsupported OpenRouter output schema reference: {reference}"
        )
    return target


def _array_index(value: str) -> int:
    """Parse the array-index form of a JSON Pointer token."""
    if (
        not value.isascii()
        or not value.isdecimal()
        or (len(value) > 1 and value[0] == "0")
    ):
        raise ValueError("Invalid array index")
    return int(value)


def _adjust_schema(schema: dict[str, Any] | bool) -> None:
    """Make optional output fields required and nullable for strict providers."""
    if isinstance(schema, bool):
        return

    for keyword in ("$defs", "definitions"):
        for definition in schema.get(keyword, {}).values():
            _adjust_schema(definition)
    for keyword in ("anyOf", "oneOf", "allOf", "prefixItems"):
        for variant in schema.get(keyword, []):
            _adjust_schema(variant)
    for keyword in ("items", "additionalProperties", "contains"):
        if keyword in schema:
            _adjust_schema(schema[keyword])

    if "properties" in schema:
        properties = schema["properties"]
        required = schema.setdefault("required", [])
        for name, prop in properties.items():
            _adjust_schema(prop)
            if name not in required:
                properties[name] = _make_nullable(prop)
                required.append(name)


def _make_nullable(schema: dict[str, Any] | bool) -> dict[str, Any]:
    """Allow null without weakening the non-null schema's constraints."""
    if (
        isinstance(schema, bool)
        or "type" not in schema
        or schema.keys() & {"$ref", "const", "anyOf", "oneOf", "allOf", "not"}
    ):
        return {"anyOf": [schema, {"type": "null"}]}

    schema_type = schema["type"]
    types = [schema_type] if isinstance(schema_type, str) else schema_type
    if "null" not in types:
        types.append("null")
    schema["type"] = types
    if "enum" in schema and None not in schema["enum"]:
        schema["enum"].append(None)
    return schema
