"""ONVIF util."""

from __future__ import annotations

from typing import Any

from zeep.exceptions import Fault

from .models import Event


def extract_event_source_from_uid(uid: str) -> str:
    """Extract event source from uid (third element after splitting by underscore)."""
    parts = uid.split("_")
    return parts[2] if len(parts) > 2 else ""


def build_event_entity_names(events: list[Event]) -> dict[str, str]:
    """Build entity names for events, with source appended for duplicates.

    When multiple events share the same base name, the source identifier
    is appended to distinguish them.

    Args:
        events: List of events to build entity names for.

    Returns:
        Dictionary mapping event UIDs to their entity names.

    """
    # Count how many events have the same base name
    name_counts: dict[str, int] = {}
    for event in events:
        name_counts[event.name] = name_counts.get(event.name, 0) + 1

    # Build entity names, appending source when there are duplicates
    entity_names: dict[str, str] = {}
    for event in events:
        if name_counts[event.name] > 1:
            source = extract_event_source_from_uid(event.uid)
            if source:
                entity_names[event.uid] = f"{event.name} {source}"
            else:
                entity_names[event.uid] = event.name
        else:
            entity_names[event.uid] = event.name

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
