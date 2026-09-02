"""Tests for shared GeoSphere Austria warning helpers."""

from pygeosphere_warnings import (
    LocationWarnings,
    WarningLevel,
    WarningType,
    WeatherWarning,
)
import pytest

from homeassistant.components.geosphere_austria_warnings.const import DOMAIN
from homeassistant.components.geosphere_austria_warnings.warnings import (
    LEVEL_NONE,
    highest_warning_level,
    select_highest_warning,
    sort_warnings,
    warning_sensor_attributes,
)

from tests.common import load_json_object_fixture


@pytest.fixture
def warnings() -> list[WeatherWarning]:
    """Return warnings parsed from the deterministic API fixture."""
    location_warnings = LocationWarnings.from_api(
        load_json_object_fixture("get_warnings_for_coords.json", DOMAIN)
    )
    return location_warnings.warnings


def test_sort_warnings_is_deterministic(warnings: list[WeatherWarning]) -> None:
    """Test actionability ranking is independent of source order.

    The fixture contains no overlapping warnings of the same type and level.
    Equal-ranked warnings are ordered by their end time: orange rain before
    orange storm, and yellow thunderstorm before demoted orange heat.
    """
    sorted_warnings = sort_warnings(warnings)
    sorted_again = sort_warnings(reversed(warnings))

    expected = [
        (4149, 12),
        (4150, 52),
        (4149, 31),
        (4150, 61),
        (4837, 2),
        (10, 51),
        (10, 11),
    ]
    assert [
        (warning.warning_id, warning.course_id) for warning in sorted_warnings
    ] == expected
    assert [
        (warning.warning_id, warning.course_id) for warning in sorted_again
    ] == expected


def test_select_highest_warning_uses_severity_then_end_time(
    warnings: list[WeatherWarning],
) -> None:
    """Test orange warnings outrank yellow and earlier end wins within orange."""
    selected = select_highest_warning(warnings)

    assert selected is not None
    assert selected.level == WarningLevel.ORANGE
    assert selected.warning_type == WarningType.STORM
    assert selected.end.isoformat() == "2023-03-27T18:00:00+00:00"


def test_highest_warning_level(warnings: list[WeatherWarning]) -> None:
    """Test highest-level values and the empty-bucket value."""
    assert highest_warning_level(warnings) == "orange"
    assert highest_warning_level([]) == LEVEL_NONE


def test_select_highest_warning_prefers_storm_over_concurrent_heat(
    warnings: list[WeatherWarning],
) -> None:
    """Test acute orange storm wins over concurrent demoted yellow heat."""
    concurrent_warnings = [
        warning
        for warning in warnings
        if warning.start.date().isoformat() == "2023-03-27"
    ]

    selected = select_highest_warning(concurrent_warnings)

    assert selected is not None
    assert selected.course_id == 12
    assert selected.warning_type == WarningType.STORM


def test_sort_warnings_demotes_sustained_heat_below_acute_thunderstorm(
    warnings: list[WeatherWarning],
) -> None:
    """Test all-day orange heat ranks below concurrent yellow thunderstorm."""
    heat_and_thunderstorm = [
        warning
        for warning in warnings
        if warning.warning_type in {WarningType.HEAT, WarningType.THUNDERSTORM}
    ]

    sorted_warnings = sort_warnings(heat_and_thunderstorm)

    assert [warning.course_id for warning in sorted_warnings] == [2, 51, 11]


def test_highest_warning_level_ignores_type_demotion(
    warnings: list[WeatherWarning],
) -> None:
    """Test severity reflects orange heat despite its display demotion."""
    heat_and_thunderstorm = [
        warning
        for warning in warnings
        if warning.warning_type in {WarningType.HEAT, WarningType.THUNDERSTORM}
    ]

    assert highest_warning_level(heat_and_thunderstorm) == "orange"


def test_select_highest_warning_prefers_acute_over_sustained(
    warnings: list[WeatherWarning],
) -> None:
    """Test a concurrent yellow thunderstorm wins over orange all-day heat."""
    concurrent_warnings = [
        warning
        for warning in warnings
        if warning.start.date().isoformat() == "2023-03-29"
        and warning.warning_type in {WarningType.HEAT, WarningType.THUNDERSTORM}
    ]

    selected = select_highest_warning(concurrent_warnings)

    assert selected is not None
    assert selected.course_id == 2
    assert selected.warning_type == WarningType.THUNDERSTORM


def test_ranking_tie_between_equal_levels_prefers_soonest_end() -> None:
    """Test the case of an all-day warning vs. a narrow-window warning.

    An all-day orange heat warning and a yellow thunderstorm warning active
    only mid-afternoon are equally ranked once heat is demoted below its
    nominal level; the thunderstorm, ending soonest, must win the tie rather
    than the heat warning's earlier (midnight) start time. Constructed
    directly since the fixture doesn't contain a same-level tie case.
    """
    all_day_heat = WeatherWarning(
        warning_id=100,
        change_id=1,
        course_id=1,
        warning_type=WarningType.HEAT,
        level=WarningLevel.ORANGE,
        start="2023-03-27T00:00:00+00:00",
        end="2023-03-27T23:59:00+00:00",
        text="",
        impacts="",
        recommendations="",
        meteo_text="",
        update_reason="",
    )
    afternoon_thunderstorm = WeatherWarning(
        warning_id=200,
        change_id=1,
        course_id=1,
        warning_type=WarningType.THUNDERSTORM,
        level=WarningLevel.YELLOW,
        start="2023-03-27T13:00:00+00:00",
        end="2023-03-27T15:00:00+00:00",
        text="",
        impacts="",
        recommendations="",
        meteo_text="",
        update_reason="",
    )

    selected = select_highest_warning([all_day_heat, afternoon_thunderstorm])

    assert selected is not None
    assert selected.warning_id == 200
    assert highest_warning_level([all_day_heat, afternoon_thunderstorm]) == "orange"


def test_warning_sensor_attributes_are_flat_and_minimal(
    warnings: list[WeatherWarning],
) -> None:
    """Test that sensor attributes expose only the selected warning details."""
    selected = select_highest_warning(warnings)
    assert selected is not None

    assert warning_sensor_attributes([selected]) == {
        "type": "storm",
        "start": "2023-03-27T08:00:00+00:00",
        "end": "2023-03-27T18:00:00+00:00",
        "warning_id": 4149,
    }

    attributes = warning_sensor_attributes([selected])
    assert set(attributes) == {"type", "start", "end", "warning_id"}
    assert warning_sensor_attributes([]) == {}
