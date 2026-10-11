"""Shared helper functions for the De Lijn integration."""

from pydelijn import Stop


def stop_title(stop: Stop) -> str:
    """Return the display title for a stop."""
    if stop.municipality:
        return f"{stop.name}, {stop.municipality}"
    return stop.name


def stop_label(stop: Stop) -> str:
    """Return the select option label for a stop."""
    if stop.municipality:
        label = f"{stop.name}, {stop.municipality} ({stop.number})"
    else:
        label = f"{stop.name} ({stop.number})"
    if stop.distance is not None:
        label += f" – {stop.distance} m"
    return label


def stop_delijn_url(stop_number: str) -> str:
    """Return the delijn.be page URL for a stop number."""
    return f"https://www.delijn.be/nl/haltes/{stop_number}/"


def stop_map_url(stop: Stop) -> str:
    """Return an OpenStreetMap URL for a stop.

    Falls back to the delijn.be page when coordinates are unknown; every
    real Stop has coordinates, so this is defensive only.
    """
    if stop.latitude is not None and stop.longitude is not None:
        return (
            "https://www.openstreetmap.org/?mlat="
            f"{stop.latitude}&mlon={stop.longitude}"
            f"#map=19/{stop.latitude}/{stop.longitude}"
        )
    return stop_delijn_url(stop.number)
