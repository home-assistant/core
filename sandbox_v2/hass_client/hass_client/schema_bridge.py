"""Sandbox-side voluptuous schema serialisation.

The sandbox owns the real :class:`voluptuous.Schema` for every flow form
and registered service. Main is the renderer / call site and needs a
JSON-safe representation it can hand to the frontend (for forms) and to
:meth:`hass.services.async_register` (for service-call validation). We
reuse :func:`voluptuous_serialize.convert` with HA's
:func:`cv.custom_serializer` so selectors and HA-specific types come out
in the exact shape the frontend already understands.

The reverse path (build a usable :class:`vol.Schema` on main from a
serialised list) lives in
``homeassistant/components/sandbox_v2/schema_bridge.py``.
"""

from typing import Any

import voluptuous_serialize

from homeassistant.helpers import config_validation as cv


def serialize_schema(schema: Any) -> list[dict[str, Any]] | None:
    """Return a JSON-safe rendering of ``schema``.

    Returns ``None`` for ``None``, an unhandled scalar (non-mapping)
    schema, or any schema voluptuous_serialize refuses — that gives the
    caller a clear "no schema came across" signal rather than partial
    nonsense. Mapping schemas come out as the list-of-fields shape the
    HA frontend already renders.
    """
    if schema is None:
        return None
    try:
        rendered = voluptuous_serialize.convert(
            schema, custom_serializer=cv.custom_serializer
        )
    except (ValueError, TypeError):
        return None
    if not isinstance(rendered, list):
        return None
    return rendered


__all__ = ["serialize_schema"]
