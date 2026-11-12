"""Sandbox-side probatio schema serialisation."""

import logging
from typing import Any

import probatio

from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)


def serialize_schema(schema: Any) -> list[dict[str, Any]] | None:
    """Return a JSON-safe rendering of ``schema``."""
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
