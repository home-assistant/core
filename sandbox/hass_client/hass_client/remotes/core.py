"""Shared helpers for remote Home Assistant mirrors."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from homeassistant.core import Context
from homeassistant.util import dt as dt_util


def parse_datetime(value: float | str | None) -> datetime:
    """Parse a Home Assistant timestamp."""
    if isinstance(value, int | float):
        return dt_util.utc_from_timestamp(float(value))
    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        if parsed is not None:
            return parsed
    return dt_util.utcnow()


def context_from_payload(payload: Mapping[str, Any] | None) -> Context | None:
    """Build a Home Assistant context from websocket payload data."""
    if not payload:
        return None
    return Context(
        user_id=payload.get("user_id"),
        parent_id=payload.get("parent_id"),
        id=payload.get("id"),
    )

