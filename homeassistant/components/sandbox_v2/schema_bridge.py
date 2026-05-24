"""Main-side reconstruction of voluptuous schemas serialised by the sandbox.

The sandbox sends a list-of-fields rendering (the same shape
:func:`voluptuous_serialize.convert` would produce against
:func:`cv.custom_serializer`). We rebuild a :class:`vol.Schema` from it
so:

* :meth:`hass.services.async_register` gets a real schema (good input
  passes, blatantly bad input is rejected before we round-trip to the
  sandbox).
* The flow-manager view's :func:`_prepare_result_json` can re-render the
  same list back through :func:`voluptuous_serialize.convert` for the
  frontend.

The reconstruction is intentionally permissive: the sandbox runs the
real validator on the actual call, so main only needs enough structure
for forms to render and obviously-broken input to be caught. Unknown
field types fall through to a pass-through validator.
"""

from collections.abc import Iterable
from typing import Any

import voluptuous as vol

_SCHEMA_TYPES_BY_NAME: dict[str, type] = {
    "string": str,
    "integer": int,
    "float": float,
    "boolean": bool,
}


def reconstruct_schema(
    serialized: list[dict[str, Any]] | None,
) -> vol.Schema | None:
    """Build a :class:`vol.Schema` from the wire form.

    Returns ``None`` for an empty list (no fields) or ``None`` input so
    callers can short-circuit straight to ``schema=None``.
    """
    if not serialized:
        return None
    fields: dict[Any, Any] = {}
    for entry in serialized:
        name = entry.get("name")
        if name is None:
            continue
        marker_cls = vol.Required if entry.get("required") else vol.Optional
        kwargs: dict[str, Any] = {}
        if "default" in entry:
            kwargs["default"] = entry["default"]
        if "description" in entry:
            kwargs["description"] = entry["description"]
        marker = marker_cls(name, **kwargs)
        fields[marker] = _validator_from_entry(entry)
    return vol.Schema(fields)


def _validator_from_entry(entry: dict[str, Any]) -> Any:
    """Best-effort inverse of :func:`voluptuous_serialize.convert` per field."""
    type_name = entry.get("type")
    if type_name in _SCHEMA_TYPES_BY_NAME:
        return _SCHEMA_TYPES_BY_NAME[type_name]
    if type_name == "select":
        options = entry.get("options") or []
        values = _select_values(options)
        if values:
            return vol.In(values)
    # Selectors, expandable sections, constants, datetime/format — the
    # sandbox owns the strict validator; on main, accept any value so the
    # caller's payload reaches the sandbox-side handler.
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
