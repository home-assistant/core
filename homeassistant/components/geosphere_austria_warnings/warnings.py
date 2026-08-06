"""Shared helpers for GeoSphere Austria weather warnings."""

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from pygeosphere_warnings import WarningLevel, WarningType, WeatherWarning


LEVEL_NONE = "none"

WARNING_TYPE_SLUGS: Mapping[WarningType, str] = {
    WarningType.STORM: "storm",
    WarningType.RAIN: "rain",
    WarningType.SNOW: "snow",
    WarningType.BLACK_ICE: "black_ice",
    WarningType.THUNDERSTORM: "thunderstorm",
    WarningType.HEAT: "heat",
    WarningType.COLD: "cold",
}

WARNING_LEVEL_SLUGS: Mapping[WarningLevel, str] = {
    WarningLevel.YELLOW: "yellow",
    WarningLevel.ORANGE: "orange",
    WarningLevel.RED: "red",
}


def warning_type_slug(warning_type: WarningType) -> str:
    """Return the stable slug for a warning type."""
    try:
        return WARNING_TYPE_SLUGS[warning_type]
    except KeyError as err:
        raise ValueError(f"Unsupported GeoSphere warning type: {warning_type!r}") from err


def warning_level_slug(level: WarningLevel) -> str:
    """Return the stable slug for a warning level."""
    try:
        return WARNING_LEVEL_SLUGS[level]
    except KeyError as err:
        raise ValueError(f"Unsupported GeoSphere warning level: {level!r}") from err


def warning_sort_key(warning: WeatherWarning) -> tuple[int, datetime, int, int, int, str]:
    """Return the deterministic ordering key for a warning.

    Warnings with a higher level sort first. For equal levels, the warning with
    the earliest start time sorts first. The remaining fields provide stable
    tie-breakers.
    """
    return (
        -warning.level.value,
        warning.start,
        warning.warning_id,
        warning.change_id,
        warning.course_id,
        warning_type_slug(warning.warning_type),
    )


def sort_warnings(warnings: Iterable[WeatherWarning]) -> list[WeatherWarning]:
    """Return warnings in deterministic highest-first order."""
    return sorted(warnings, key=warning_sort_key)


def select_highest_warning(
    warnings: Iterable[WeatherWarning],
) -> WeatherWarning | None:
    """Return the highest-priority warning, or ``None`` for an empty bucket."""
    return next(iter(sort_warnings(warnings)), None)


def warning_sensor_attributes(
    warnings: Iterable[WeatherWarning],
) -> dict[str, Any]:
    """Return the four agreed attributes for the selected warning.

    The full warning payload is intentionally not exposed on sensor entities.
    """
    warning = select_highest_warning(warnings)
    if warning is None:
        return {}

    return {
        "type": warning_type_slug(warning.warning_type),
        "start": warning.start.isoformat(),
        "end": warning.end.isoformat(),
        "warning_id": warning.warning_id,
    }


def serialize_warning(warning: WeatherWarning) -> dict[str, Any]:
    """Convert a warning into a fully JSON-serializable response object."""
    return {
        "warning_id": warning.warning_id,
        "change_id": warning.change_id,
        "course_id": warning.course_id,
        "type": warning_type_slug(warning.warning_type),
        "level": warning_level_slug(warning.level),
        "start": warning.start.isoformat(),
        "end": warning.end.isoformat(),
        "text": warning.text,
        "impacts": warning.impacts,
        "recommendations": warning.recommendations,
        "meteo_text": warning.meteo_text,
        "update_reason": warning.update_reason,
    }


def serialize_warnings(
    warnings: Iterable[WeatherWarning],
) -> list[dict[str, Any]]:
    """Serialize warnings in the shared deterministic order."""
    return [serialize_warning(warning) for warning in sort_warnings(warnings)]


def highest_warning_level(warnings: Iterable[WeatherWarning]) -> str:
    """Return the highest warning level, or ``none`` for an empty bucket."""
    warning = select_highest_warning(warnings)
    if warning is None:
        return LEVEL_NONE
    return warning_level_slug(warning.level)
