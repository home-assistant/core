"""State attributes models."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.engine.row import Row

from homeassistant.util.json import json_loads_object

EMPTY_JSON_OBJECT = "{}"
_LOGGER = logging.getLogger(__name__)


def decode_attributes_from_row(
    row: Row, attr_cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Decode attributes from a database row."""
    source: str | None = getattr(row, "shared_attrs", None) or getattr(
        row, "attributes", None
    )
    if not source or source == EMPTY_JSON_OBJECT:
        return {}
    if (attributes := attr_cache.get(source)) is not None:
        return attributes
    try:
        attr_cache[source] = attributes = json_loads_object(source)
    except ValueError:
        _LOGGER.exception("Error converting row to state attributes: %s", source)
        attr_cache[source] = attributes = {}
    return attributes
