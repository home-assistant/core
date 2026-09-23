"""Sandbox-side probatio schema serialisation.

The sandbox owns the real :class:`probatio.Schema` for every flow form
and registered service. Main is the renderer / call site and needs a
JSON-safe representation it can hand to the frontend (for forms) and to
:meth:`hass.services.async_register` (for service-call validation). We
reuse :func:`probatio.to_field_list` with HA's
:func:`cv.custom_serializer` so selectors and HA-specific types come out
in the exact shape the frontend already understands.

The reverse path (build a usable :class:`probatio.Schema` on main from a
serialised list) lives in
``homeassistant/components/sandbox/schema_bridge.py``.
"""

import logging
from typing import Any

import probatio

from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)


def serialize_schema(schema: Any) -> list[dict[str, Any]] | None:
    """Return a JSON-safe rendering of ``schema``.

    Returns ``None`` for ``None``, an unhandled scalar (non-mapping)
    schema, or any schema serialisation fails on — that gives the caller
    a clear "no schema came across" signal rather than partial nonsense
    or a crash. Mapping schemas come out as the list-of-fields shape the
    HA frontend already renders.

    The fallback is deliberately broad. A registered service or flow form
    may carry a schema with an exotic custom validator that
    ``probatio.to_field_list`` chokes on in ways beyond ``ValueError`` /
    ``TypeError`` (a validator raising ``probatio.Invalid``, ``AttributeError``,
    a library-specific exception, …). Letting any of those propagate would
    drop the whole ``register_service`` / flow push, so main would never
    learn the service/form exists. Degrading to ``schema=None`` instead
    keeps the registration: main installs the service with no schema and
    the sandbox's own handler still runs full validation when the call
    lands. We log the failure (with the schema repr) so a genuinely
    unserialisable schema is visible rather than silently lossy.
    """
    if schema is None:
        return None
    try:
        rendered = probatio.to_field_list(
            schema, custom_serializer=cv.custom_serializer
        )
    except Exception:  # noqa: BLE001 — any serialise failure must degrade, not drop
        _LOGGER.warning(
            "Schema did not survive serialisation; main falls back to no schema "
            "(sandbox still validates). Schema: %r",
            schema,
        )
        return None
    if not isinstance(rendered, list):
        return None
    return rendered


__all__ = ["serialize_schema"]
