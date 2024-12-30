"""TypedDict definitions for DVSPortal integration."""

from typing import Any, TypedDict


class DVSPortalData(TypedDict):
    """TypedDict for DVSPortal coordinator data."""

    default_code: str
    default_type_id: str
    balance: dict[str, Any]  # Assuming balance has nested data
    active_reservations: dict[str, Any]
    historic_reservations: dict[str, Any]
    known_license_plates: dict[str, str]
