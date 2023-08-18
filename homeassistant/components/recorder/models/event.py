"""Models events in for Recorder."""
from __future__ import annotations


def extract_event_type_ids(
    event_type_to_event_type_id: dict[str, int | None],
) -> list[int]:
    """Extract event_type ids from event_type_to_event_type_id."""
    return [
        event_type_id
        for event_type_id in event_type_to_event_type_id.values()
        if event_type_id is not None
    ]
