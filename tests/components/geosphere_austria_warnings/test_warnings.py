"""Tests for shared GeoSphere Austria warning helpers."""

from datetime import UTC, datetime

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


def test_sort_warnings_uses_severity_then_end_time(
    warnings: list[WeatherWarning],
) -> None:
    """Test orange warnings outrank yellow and earlier end wins within orange."""
    selected = sort_warnings(warnings)[0]

    assert selected.level == WarningLevel.ORANGE
    assert selected.warning_type == WarningType.STORM
    assert selected.end.isoformat() == "2023-03-27T16:00:00+00:00"


def test_highest_warning_level(warnings: list[WeatherWarning]) -> None:
    """Test highest-level values and the empty-bucket value."""
    assert highest_warning_level(warnings) == "orange"
    assert highest_warning_level([]) == LEVEL_NONE


def test_sort_warnings_prefers_storm_over_concurrent_heat(
    warnings: list[WeatherWarning],
) -> None:
    """Test acute orange storm wins over concurrent demoted yellow heat."""
    at = datetime(2023, 3, 27, 10, 0, tzinfo=UTC)
    concurrent_warnings = [
        warning for warning in warnings if warning.start <= at < warning.end
    ]

    assert {warning.warning_type for warning in concurrent_warnings} == {
        WarningType.HEAT,
        WarningType.STORM,
    }

    selected = sort_warnings(concurrent_warnings)[0]

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


def test_sort_warnings_prefers_acute_over_sustained(
    warnings: list[WeatherWarning],
) -> None:
    """Test a concurrent yellow thunderstorm wins over orange all-day heat."""
    at = datetime(2023, 3, 29, 12, 0, tzinfo=UTC)
    concurrent_warnings = [
        warning
        for warning in warnings
        if warning.start <= at < warning.end
        and warning.warning_type in {WarningType.HEAT, WarningType.THUNDERSTORM}
    ]

    assert {warning.warning_type for warning in concurrent_warnings} == {
        WarningType.HEAT,
        WarningType.THUNDERSTORM,
    }

    selected = sort_warnings(concurrent_warnings)[0]

    assert selected.course_id == 2
    assert selected.warning_type == WarningType.THUNDERSTORM


def test_ranking_tie_between_equal_levels_prefers_soonest_end() -> None:
    """Test that the earliest end time breaks ties between equally ranked warnings."""
    all_day_heat = WeatherWarning(
        warning_id=100,
        change_id=1,
        course_id=1,
        warning_type=WarningType.HEAT,
        level=WarningLevel.ORANGE,
        start=datetime(2023, 3, 26, 22, 0, tzinfo=UTC),
        end=datetime(2023, 3, 27, 21, 59, tzinfo=UTC),
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
        start=datetime(2023, 3, 27, 11, 0, tzinfo=UTC),
        end=datetime(2023, 3, 27, 13, 0, tzinfo=UTC),
        text="",
        impacts="",
        recommendations="",
        meteo_text="",
        update_reason="",
    )

    selected = sort_warnings([all_day_heat, afternoon_thunderstorm])[0]

    assert selected.warning_id == 200
    assert highest_warning_level([all_day_heat, afternoon_thunderstorm]) == "orange"


def test_warning_sensor_attributes_are_flat_and_minimal(
    warnings: list[WeatherWarning],
) -> None:
    """Test that sensor attributes expose only the selected warning details."""
    sorted_warnings = sort_warnings(warnings)

    assert warning_sensor_attributes(sorted_warnings) == {
        "type": "storm",
        "level": "orange",
        "start": "2023-03-27T06:00:00+00:00",
        "end": "2023-03-27T16:00:00+00:00",
        "warning_id": 4149,
    }

    attributes = warning_sensor_attributes(sorted_warnings)
    assert set(attributes) == {"type", "level", "start", "end", "warning_id"}
    assert warning_sensor_attributes([]) == {}


def test_warning_sensor_attributes_include_diverging_warning_level() -> None:
    """Test that sensor attributes expose only the selected warning details."""
    all_day_heat = WeatherWarning(
        warning_id=100,
        change_id=1,
        course_id=1,
        warning_type=WarningType.HEAT,
        level=WarningLevel.ORANGE,
        start=datetime(2023, 3, 26, 22, 0, tzinfo=UTC),
        end=datetime(2023, 3, 27, 21, 59, tzinfo=UTC),
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
        start=datetime(2023, 3, 27, 11, 0, tzinfo=UTC),
        end=datetime(2023, 3, 27, 13, 0, tzinfo=UTC),
        text="",
        impacts="",
        recommendations="",
        meteo_text="",
        update_reason="",
    )

    all_warnings = [all_day_heat, afternoon_thunderstorm]
    sorted_warnings = sort_warnings(all_warnings)

    selected = sorted_warnings[0]
    assert selected.warning_id == 200  # thunderstorm wins the tie

    assert warning_sensor_attributes(sorted_warnings) == {
        "type": "thunderstorm",
        "start": "2023-03-27T11:00:00+00:00",
        "end": "2023-03-27T13:00:00+00:00",
        "warning_id": 200,
        "level": "yellow",
    }

    attributes = warning_sensor_attributes(sorted_warnings)
    assert set(attributes) == {"type", "start", "end", "warning_id", "level"}
