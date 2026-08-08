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

SUSTAINED_WARNING_TYPES: frozenset[WarningType] = frozenset(
    {WarningType.HEAT, WarningType.COLD}
)
RANKING_DEMOTION = 1


def warning_type_slug(warning_type: WarningType) -> str:
    """Return the stable slug for a warning type."""
    try:
        return WARNING_TYPE_SLUGS[warning_type]
    except KeyError as err:
        raise ValueError(
            f"Unsupported GeoSphere warning type: {warning_type!r}"
        ) from err


def warning_level_slug(level: WarningLevel) -> str:
    """Return the stable slug for a warning level."""
    try:
        return WARNING_LEVEL_SLUGS[level]
    except KeyError as err:
        raise ValueError(f"Unsupported GeoSphere warning level: {level!r}") from err


def _ranking_level(warning: WeatherWarning) -> int:
    """Return the level value used for ordering, adjusted for warning type.

    Sustained/ambient types (heat, cold) are demoted by one tier relative to
    acute/event types when ranking warnings against each other, since they
    describe a background condition rather than something to react to right
    now. This never affects the warning's actual, reported level.
    """
    demotion = (
        RANKING_DEMOTION if warning.warning_type in SUSTAINED_WARNING_TYPES else 0
    )
    return warning.level.value - demotion


def warning_sort_key(
    warning: WeatherWarning,
) -> tuple[int, datetime, datetime, int, int, int, str]:
    """Return the deterministic ordering key for a warning.

    Warnings with a higher ranking level sort first. For equal ranking levels, the
    warning with the earliest end time sorts first, followed by its start time.
    The remaining fields provide stable tie-breakers.
    """
    return (
        -_ranking_level(warning),
        warning.end,
        warning.start,
        warning.warning_id,
        warning.change_id,
        warning.course_id,
        warning_type_slug(warning.warning_type),
    )


def sort_warnings(warnings: Iterable[WeatherWarning]) -> list[WeatherWarning]:
    """Return warnings in deterministic, actionability-ranked order.

    This ordering is used for display and for selecting the "featured"
    warning (see ``select_highest_warning``); it is intentionally not pure
    severity order. For the true worst-case severity, use
    ``highest_warning_level`` instead.
    """
    return sorted(warnings, key=warning_sort_key)


def select_highest_warning(
    warnings: Iterable[WeatherWarning],
) -> WeatherWarning | None:
    """Return the highest-priority warning, or ``None`` for an empty bucket.

    Coordinator provides sorted lists, this makes this function robust and to
    _always_ return the highest-priority warning. Also allows for unsorted
    fixtures, otherwise fixtures require manual sorting with every update of
    sorting logic.
    """
    sorted_warnings = sort_warnings(warnings)
    return sorted_warnings[0] if sorted_warnings else None


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


def highest_warning_level(warnings: Iterable[WeatherWarning]) -> str:
    """Return the highest *actual* warning level, or ``none`` for an empty bucket.

    Deliberately independent of ``sort_warnings``' type-adjusted ranking: the
    reported level must reflect true worst-case severity, e.g. a red heat
    warning must never be masked by a concurrent yellow thunderstorm.
    """
    levels = [warning.level.value for warning in warnings]
    if not levels:
        return LEVEL_NONE
    return warning_level_slug(WarningLevel(max(levels)))
