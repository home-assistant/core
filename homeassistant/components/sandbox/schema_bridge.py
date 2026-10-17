"""Main-side reconstruction of voluptuous schemas serialised by the sandbox."""

from collections.abc import Iterable
import logging
from typing import Any

import probatio

from homeassistant import data_entry_flow
from homeassistant.helpers import selector

_LOGGER = logging.getLogger(__name__)

_SCHEMA_TYPES_BY_NAME: dict[str, type] = {
    "string": str,
    "integer": int,
    "float": float,
    "boolean": bool,
}


def reconstruct_schema(
    serialized: list[dict[str, Any]] | None,
) -> probatio.Schema | None:
    """Build a :class:`probatio.Schema` from the wire form."""
    if not serialized:
        return None
    fields: dict[Any, Any] = {}
    for entry in serialized:
        name = entry.get("name")
        if name is None:
            continue
        marker_cls = probatio.Required if entry.get("required") else probatio.Optional
        kwargs: dict[str, Any] = {}
        if "default" in entry:
            kwargs["default"] = entry["default"]
        if "description" in entry:
            kwargs["description"] = entry["description"]
        marker = marker_cls(name, **kwargs)
        fields[marker] = _validator_from_entry(entry)
    return probatio.Schema(fields)


def _validator_from_entry(entry: dict[str, Any]) -> Any:
    """Inverse of :func:`probatio.to_field_list` per field."""
    # A selector field carries its config under ``selector`` (no ``type``);
    # rebuild the real Selector so it re-serialises to the same shape.
    if "selector" in entry:
        try:
            return selector.selector(entry["selector"])
        except probatio.Invalid:
            _LOGGER.warning(
                "Could not rebuild selector from %r; using pass-through",
                entry["selector"],
            )
            return _passthrough
    type_name = entry.get("type")
    if type_name == "expandable":
        # An ``data_entry_flow.section`` — rebuild it with its nested schema
        # so the frontend still renders the collapsible section.
        nested = reconstruct_schema(entry.get("schema")) or probatio.Schema({})
        collapsed = not entry.get("expanded", True)
        return data_entry_flow.section(nested, {"collapsed": collapsed})
    if type_name in _SCHEMA_TYPES_BY_NAME:
        return _SCHEMA_TYPES_BY_NAME[type_name]
    if type_name == "select":
        options = entry.get("options") or []
        values = _select_values(options)
        if values:
            return probatio.In(values)
    # Constants, datetime/format, and other shapes we don't reconstruct —
    # the sandbox owns the strict validator; on main, accept any value so
    # the caller's payload reaches the sandbox-side handler.
    return _passthrough


def _select_values(options: Iterable[Any]) -> list[Any]:
    """Pull the value half out of a serialised select's ``options``."""
    out: list[Any] = []
    for opt in options:
        if isinstance(opt, (list, tuple)) and opt:
            out.append(opt[0])
        else:
            out.append(opt)
    return out


def _passthrough(value: Any) -> Any:
    """Identity validator — sandbox-side handler does the real validation."""
    return value


__all__ = ["reconstruct_schema"]
