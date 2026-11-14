"""Convert output schemas to OpenAI's supported JSON Schema subset for strict structured output format."""
# Documentation: https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses#supported-schemas

from collections.abc import Iterator
from copy import deepcopy
import logging
from typing import Any
from urllib.parse import unquote

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_ANNOTATIONS = {
    "default",
    "examples",
    "$comment",
    "deprecated",
    "readOnly",
    "writeOnly",
}
_UNSUPPORTED_KEYWORDS = {
    "oneOf",
    "not",
    "dependentRequired",
    "dependentSchemas",
    "if",
    "then",
    "else",
}
_SELECTOR_FORMATS = {"entity_id", "jinja2", "RFC 5646", "ISO 3166-1 alpha-2", "RGB"}
_SCHEMA_MAPS = (
    "properties",
    "$defs",
    "definitions",
    "patternProperties",
    "dependentSchemas",
)
_SCHEMA_LISTS = ("anyOf", "allOf", "prefixItems")
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


def adjust_schema(schema: dict[str, Any]) -> None:
    """Normalize known incompatibilities, preserving unfamiliar API features."""
    _stabilize_references(schema)
    _adjust_schema(schema, "$")
    if schema.get("type") != "object" or "anyOf" in schema:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="structured_output_object_root",
        )


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
    # References now target $defs, so the duplicate definitions can be discarded.
    for node in _walk_schemas(schema):
        node.pop("definitions", None)
        if "$ref" in node:
            node["$ref"] = replacements[node["$ref"]]


def _reference_parts(reference: str) -> list[str]:
    """Decode a local JSON Pointer, including URI fragment escaping."""
    if reference == "#":
        return []
    if not reference.startswith("#/"):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="schema_reference_unsupported",
            translation_placeholders={"reference": reference},
        )
    return [
        part.replace("~1", "/").replace("~0", "~")
        for part in unquote(reference[2:]).split("/")
    ]


def _resolve_reference(reference: str, root: dict[str, Any]) -> dict[str, Any]:
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
            translation_domain=DOMAIN,
            translation_key="schema_reference_invalid",
            translation_placeholders={"reference": reference},
        ) from err
    if not isinstance(target, dict):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="schema_reference_unsupported",
            translation_placeholders={"reference": reference},
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


def _flatten_all_of(schema: dict[str, Any], path: str) -> None:
    """Unwrap intersections only when sibling constraints can all be retained."""
    while "allOf" in schema:
        branches = schema["allOf"]
        if len(branches) != 1 or not isinstance(branches[0], dict):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="schema_all_of_unsupported",
                translation_placeholders={"path": path},
            )
        branch = branches[0]
        siblings = schema.keys() - {"allOf", "description", "title"} - _ANNOTATIONS
        conflicts = {
            key for key in siblings & branch.keys() if schema[key] != branch[key]
        }
        if conflicts:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="schema_all_of_conflict",
                translation_placeholders={
                    "path": path,
                    "conflicts": ", ".join(sorted(conflicts)),
                },
            )
        del schema["allOf"]
        for key, value in branch.items():
            schema.setdefault(key, value)


def _adjust_reference(schema: dict[str, Any], path: str, *, nullable: bool) -> None:
    """Keep references bare and preserve annotations on nullable wrappers."""
    if siblings := schema.keys() - {"$ref", "title", "description"}:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="schema_reference_siblings",
            translation_placeholders={
                "path": path,
                "siblings": ", ".join(sorted(siblings)),
            },
        )
    annotations: dict[str, Any] = {
        keyword: schema.pop(keyword)
        for keyword in ("title", "description")
        if keyword in schema
    }
    if nullable:
        _make_nullable(schema)
        schema.update(annotations)
    elif annotations:
        _LOGGER.debug(
            "Removed reference annotations %s from OpenAI output schema at %s",
            ", ".join(annotations),
            path,
        )


def _adjust_schema(
    schema: dict[str, Any] | bool, path: str, *, nullable: bool = False
) -> None:
    """Normalize nested schemas and keep unsupported enforcement out of requests."""
    if not isinstance(schema, dict):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="schema_unsupported",
            translation_placeholders={"path": path},
        )
    _flatten_all_of(schema, path)
    for keyword in _ANNOTATIONS:
        schema.pop(keyword, None)
    if unsupported := schema.keys() & _UNSUPPORTED_KEYWORDS:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="schema_keywords_unsupported",
            translation_placeholders={
                "path": path,
                "keywords": ", ".join(sorted(unsupported)),
            },
        )
    if not schema:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="schema_unsupported",
            translation_placeholders={"path": path},
        )
    if schema.get("format") in _SELECTOR_FORMATS:
        del schema["format"]
    if schema.pop("uniqueItems", None) is True:
        _LOGGER.debug(
            "Removed unsupported uniqueItems: true from OpenAI output schema at %s",
            path,
        )
    if "$ref" in schema:
        _adjust_reference(schema, path, nullable=nullable)
        return

    for name, definition in schema.get("$defs", {}).items():
        _adjust_schema(definition, f"{path}.$defs.{name}")
    for index, variant in enumerate(schema.get("anyOf", [])):
        _adjust_schema(variant, f"{path}.anyOf[{index}]")

    schema_type = schema.get("type", [])
    types = [schema_type] if isinstance(schema_type, str) else schema_type
    if "object" in types:
        if schema.get("additionalProperties", False) is not False:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="schema_object_fields_required",
                translation_placeholders={"path": path},
            )
        schema["additionalProperties"] = False
        properties = schema.setdefault("properties", {})
        required = schema.setdefault("required", [])
        for name, prop in properties.items():
            _adjust_schema(
                prop, f"{path}.properties.{name}", nullable=name not in required
            )
            if name not in required:
                required.append(name)
    if "array" in types:
        if "items" not in schema:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="schema_array_items_required",
                translation_placeholders={"path": path},
            )
        _adjust_schema(schema["items"], f"{path}.items")
    if nullable:
        _make_nullable(schema)


def _make_nullable(schema: dict[str, Any]) -> None:
    """Allow null without weakening the non-null schema's constraints."""
    if "type" not in schema or schema.keys() & {"$ref", "const", "anyOf"}:
        original = schema.copy()
        schema.clear()
        schema["anyOf"] = [original, {"type": "null"}]
        return
    schema_type = schema["type"]
    types = [schema_type] if isinstance(schema_type, str) else schema_type
    if "null" not in types:
        types.append("null")
    schema["type"] = types
    if "enum" in schema and None not in schema["enum"]:
        schema["enum"].append(None)
