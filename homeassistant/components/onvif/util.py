"""ONVIF util."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from zeep.exceptions import Fault

from .models import Event


def build_event_entity_names(events: list[Event]) -> dict[str, str]:
    """Build entity names for events, with index appended for duplicates.

    When multiple events share the same base name, a sequential index
    is appended to distinguish them (sorted by UID).

    Args:
        events: List of events to build entity names for.

    Returns:
        Dictionary mapping event UIDs to their entity names.

    """
    # Group events by name
    events_by_name: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        events_by_name[event.name].append(event)

    # Build entity names, appending index when there are duplicates
    entity_names: dict[str, str] = {}
    for name, name_events in events_by_name.items():
        if len(name_events) == 1:
            # No duplicates, use name as-is
            entity_names[name_events[0].uid] = name
            continue

        # Sort by UID and assign sequential indices
        sorted_events = sorted(name_events, key=lambda e: e.uid)
        for index, event in enumerate(sorted_events, start=1):
            entity_names[event.uid] = f"{name} {index}"

    return entity_names


def extract_subcodes_as_strings(subcodes: Any) -> list[str]:
    """Stringify ONVIF subcodes."""
    if isinstance(subcodes, list):
        return [code.text if hasattr(code, "text") else str(code) for code in subcodes]
    return [str(subcodes)]


def stringify_onvif_error(error: Exception) -> str:
    """Stringify ONVIF error."""
    if isinstance(error, Fault):
        message = error.message
        if error.detail is not None:  # checking true is deprecated
            # Detail may be a bytes object, so we need to convert it to string
            if isinstance(error.detail, bytes):
                detail = error.detail.decode("utf-8", "replace")
            else:
                detail = str(error.detail)
            message += ": " + detail
        if error.code is not None:  # checking true is deprecated
            message += f" (code:{error.code})"
        if error.subcodes is not None:  # checking true is deprecated
            message += (
                f" (subcodes:{','.join(extract_subcodes_as_strings(error.subcodes))})"
            )
        if error.actor:
            message += f" (actor:{error.actor})"
    else:
        message = str(error)
    return message or f"Device sent empty error with type {type(error)}"


def is_auth_error(error: Exception) -> bool:
    """Return True if error is an authentication error.

    Most of the tested cameras do not return a proper error code when
    authentication fails, so we need to check the error message as well.
    """
    if not isinstance(error, Fault):
        return False
    return (
        any(
            "NotAuthorized" in code
            for code in extract_subcodes_as_strings(error.subcodes)
        )
        or "auth" in stringify_onvif_error(error).lower()
    )
