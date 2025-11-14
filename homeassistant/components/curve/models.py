"""Data models for the Curve integration."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.helpers.schema_config_entry_flow import SchemaFlowError

from .const import INTERPOLATION_LINEAR, INTERPOLATION_TYPES


@dataclasses.dataclass(frozen=True)
class CurveSegment:
    """Representation of a curve segment."""

    x0: float
    y0: float
    x1: float
    y1: float
    type: str = INTERPOLATION_LINEAR
    z: float | None = None  # Used as a control point for future interpolations

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CurveSegment:
        """Create a CurveSegment from a dictionary."""
        type = data.get("type", INTERPOLATION_LINEAR)  # noqa: A001
        if type not in INTERPOLATION_TYPES:
            raise SchemaFlowError("invalid_interpolation_type")
        z_value = data.get("z")
        return cls(
            x0=float(data["x0"]),
            y0=float(data["y0"]),
            x1=float(data["x1"]),
            y1=float(data["y1"]),
            type=type,
            z=float(z_value) if z_value is not None else None,
        )

    def to_dict(self) -> dict:
        """Convert the segment to a dictionary."""
        result = dataclasses.asdict(self)
        if result["z"] is None:
            del result["z"]
        return result
