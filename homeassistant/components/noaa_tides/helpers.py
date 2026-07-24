"""Helpers for NOAA Tides integration."""


def get_station_unique_id(station_id: str) -> str:
    """Convert a station ID to a unique ID."""
    return f"{station_id.lower()}"
