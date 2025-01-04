"""TypedDict definitions for DVSPortal integration."""

from typing import TypedDict

from dvsportal import HistoricReservation, Reservation


class DVSPortalData(TypedDict):
    """TypedDict for DVSPortal coordinator data."""

    default_code: str
    default_type_id: str
    balance: float
    active_reservations: dict[str, Reservation]
    historic_reservations: dict[str, HistoricReservation]
    known_license_plates: dict[str, str]
