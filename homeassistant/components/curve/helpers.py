"""Low-level curve helper functionality."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.helpers.schema_config_entry_flow import SchemaFlowError

from .const import INTERPOLATION_STEP
from .models import CurveSegment


def interpolate_curve(x: float, segments: list[CurveSegment]) -> float:
    """Interpolate value on a piecewise curve."""
    if not segments:  # pragma: no cover
        raise ValueError("No segments provided for interpolation")

    sorted_segments = sorted(segments, key=lambda s: s.x0)

    for segment in sorted_segments:
        if segment.x0 <= x <= segment.x1:
            if segment.type == INTERPOLATION_STEP:
                return segment.y0
            # Linear interpolation
            if segment.x1 == segment.x0:  # Avoid division by zero
                return segment.y0
            t = (x - segment.x0) / (segment.x1 - segment.x0)
            return segment.y0 + t * (segment.y1 - segment.y0)

    if x < sorted_segments[0].x0:  # Before first segment
        return sorted_segments[0].y0
    return sorted_segments[-1].y1  # After last segment (or in an undefined gap)


def parse_segments(
    segments_json_or_list: str | list[dict[str, Any]],
) -> list[CurveSegment]:
    """Validate and parse the segments, either from a JSON string or raw data."""
    if isinstance(segments_json_or_list, str):
        try:
            segments_data = json.loads(segments_json_or_list)
        except json.JSONDecodeError as err:
            raise SchemaFlowError("invalid_segments_json") from err
    else:
        segments_data = segments_json_or_list

    if not isinstance(segments_data, list):
        raise SchemaFlowError("invalid_segments_json")

    if not segments_data:
        raise SchemaFlowError("no_segments")

    validated_segments = []
    for segment_data in segments_data:
        if isinstance(segment_data, list):
            try:
                # Shorthand form used in e.g. templates
                seg_dict = {
                    "x0": segment_data[0],
                    "y0": segment_data[1],
                    "x1": segment_data[2],
                    "y1": segment_data[3],
                }
                if len(segment_data) > 4:
                    seg_dict["type"] = segment_data[4]
                segment_data = seg_dict
            except IndexError:
                raise SchemaFlowError("invalid_segment_structure") from None

        if not isinstance(segment_data, dict):
            raise SchemaFlowError("invalid_segment_structure")

        try:
            segment = CurveSegment.from_dict(segment_data)
        except KeyError as err:
            raise SchemaFlowError("invalid_segment_structure") from err
        except (ValueError, TypeError) as err:
            raise SchemaFlowError("invalid_segment_values") from err

        validated_segments.append(segment)

    validated_segments.sort(key=lambda seg: seg.x0)
    return validated_segments
