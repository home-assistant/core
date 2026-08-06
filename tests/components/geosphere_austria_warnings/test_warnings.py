"""Tests for shared GeoSphere Austria warning helpers."""

import json

from pygeosphere_warnings import LocationWarnings
import pytest

from homeassistant.components.geosphere_austria_warnings.const import DOMAIN
from homeassistant.components.geosphere_austria_warnings.warnings import (
    LEVEL_NONE,
    highest_warning_level,
    select_highest_warning,
    serialize_warning,
    serialize_warnings,
    sort_warnings,
    warning_sensor_attributes,
)

from tests.common import load_json_object_fixture


@pytest.fixture
def warnings() -> list:
    """Return warnings parsed from the deterministic API fixture."""
    location_warnings = LocationWarnings.from_api(
        load_json_object_fixture("get_warnings_for_coords.json", DOMAIN)
    )
    return location_warnings.warnings


def test_sort_warnings_is_deterministic(warnings: list) -> None:
    """Test level, start time, and identifier ordering."""
    sorted_warnings = sort_warnings(warnings)
    sorted_again = sort_warnings(list(reversed(warnings)))

    assert [warning.course_id for warning in sorted_warnings] == [
        12,
        52,
        31,
        41,
        21,
        61,
    ]
    assert [warning.course_id for warning in sorted_again] == [
        warning.course_id for warning in sorted_warnings
    ]


def test_select_highest_warning_uses_level_then_start_then_ids(
    warnings: list,
) -> None:
    """Test that course_id is only a final tie-breaker."""
    advance_warnings = [warning for warning in warnings if warning.course_id != 12]

    selected = select_highest_warning(advance_warnings)

    assert selected is not None
    assert selected.course_id == 52
    assert serialize_warning(selected)["level"] == "orange"
    assert selected.start.isoformat() == "2023-03-28T06:00:00+00:00"


def test_highest_warning_level(warnings: list) -> None:
    """Test highest-level values and the empty-bucket value."""
    assert highest_warning_level(warnings) == "orange"
    assert highest_warning_level([]) == LEVEL_NONE


def test_warning_sensor_attributes_are_flat_and_minimal(warnings: list) -> None:
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


def test_serialize_warning_contains_complete_json_compatible_record(
    warnings: list,
) -> None:
    """Test complete warning serialization and stable enum slugs."""
    warning = next(item for item in warnings if item.course_id == 12)

    serialized = serialize_warning(warning)

    assert serialized == {
        "warning_id": 4149,
        "change_id": 6,
        "course_id": 12,
        "type": "storm",
        "level": "orange",
        "start": "2023-03-27T08:00:00+00:00",
        "end": "2023-03-27T18:00:00+00:00",
        "text": "Orange storm warning from Mon, 27.03.2023 08:00 until Mon, 27.03.2023 18:00",
        "impacts": "* Branches may fall and objects may be thrown around.",
        "recommendations": "* Be careful in forests, parks and avenues!",
        "meteo_text": "Strong northwest winds with gusts between 60 and 80 km/h.",
        "update_reason": "",
    }
    assert "WarningType." not in repr(serialized)
    assert "WarningLevel." not in repr(serialized)
    json.dumps(serialized)


def test_serialize_warnings_preserves_shared_sort_order(warnings: list) -> None:
    """Test serialization of a complete warning bucket."""
    serialized = serialize_warnings(list(reversed(warnings)))

    assert [warning["course_id"] for warning in serialized] == [
        12,
        52,
        31,
        41,
        21,
        61,
    ]
    assert all(isinstance(warning["start"], str) for warning in serialized)
    assert all(isinstance(warning["end"], str) for warning in serialized)
    json.dumps(serialized)
