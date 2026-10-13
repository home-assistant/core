"""Tests for location regions."""

from typing import Any

import pytest

from homeassistant.components.location.region import (
    available_regions,
    load_region,
    parse_region,
)

# A square with a hole, a counter-enclave inside the hole and a separate island
# across the antimeridian, mirroring how real borders look in GeoJSON.
REGION = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "Mainland with enclave"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                    [[4, 4], [4, 6], [6, 6], [6, 4], [4, 4]],
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {"name": "Counter-enclave and island"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[4.5, 4.5], [5.5, 4.5], [5.5, 5.5], [4.5, 5.5], [4.5, 4.5]]],
                    [[[179, -18], [180, -18], [180, -17], [179, -18]]],
                ],
            },
        },
    ],
}


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected"),
    [
        pytest.param(2, 2, True, id="mainland"),
        pytest.param(4.2, 4.2, False, id="enclave"),
        pytest.param(5, 5, True, id="counter_enclave"),
        pytest.param(-17.8, 179.8, True, id="island"),
        pytest.param(-17.2, 179.2, False, id="island_bounding_box_only"),
        pytest.param(5, 11, False, id="outside_bounding_box"),
    ],
)
def test_region_contains(latitude: float, longitude: float, expected: bool) -> None:
    """Test matching coordinates against polygons with holes."""
    assert parse_region(REGION).contains(latitude, longitude) is expected


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            id="polygon",
        ),
        pytest.param(
            {
                "type": "Polygon",
                "coordinates": [[[0, 0, 12.5], [1, 0, 13], [1, 1, 14], [0, 0, 12.5]]],
            },
            id="positions_with_altitude",
        ),
        pytest.param(
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]],
                },
            },
            id="feature",
        ),
    ],
)
def test_parse_region(data: dict[str, Any]) -> None:
    """Test parsing the supported GeoJSON objects."""
    assert parse_region(data).contains(0.25, 0.75)


@pytest.mark.parametrize(
    ("data", "error"),
    [
        pytest.param(
            {"type": "FeatureCollection", "features": []},
            "No polygons found",
            id="no_polygons",
        ),
        pytest.param(
            {"type": "Point", "coordinates": [0, 0]},
            "Unsupported GeoJSON type Point",
            id="unsupported_type",
        ),
        pytest.param([], "Invalid GeoJSON object", id="not_an_object"),
        pytest.param(
            {"type": "Polygon", "coordinates": []},
            "Polygon must have at least one ring",
            id="no_rings",
        ),
        pytest.param(
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]},
            "Linear ring must have at least four positions",
            id="short_ring",
        ),
        pytest.param(
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
            "Linear ring must be closed",
            id="open_ring",
        ),
        pytest.param(
            {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 91], [0, 0]]],
            },
            r"Invalid position \[1, 91\]",
            id="latitude_out_of_range",
        ),
        pytest.param(
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], ["1", 1], [0, 0]]]},
            r"Invalid position \['1', 1\]",
            id="position_not_a_number",
        ),
    ],
)
def test_parse_region_invalid(data: Any, error: str) -> None:
    """Test parsing invalid GeoJSON."""
    with pytest.raises(ValueError, match=error):
        parse_region(data)


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected"),
    [
        pytest.param(52.3731, 4.8922, True, id="amsterdam"),
        pytest.param(52.2215, 6.8937, True, id="enschede"),
        pytest.param(52.1103, 4.2766, True, id="scheveningen_beach"),
        pytest.param(51.4436, 4.9311, True, id="baarle_nassau"),
        pytest.param(51.43006, 4.9353, False, id="baarle_hertog_enclave"),
        pytest.param(51.4463, 4.93964, False, id="baarle_hertog_other_enclave"),
        pytest.param(12.1443, -68.2655, True, id="bonaire"),
        pytest.param(12.5211, -69.9683, False, id="aruba"),
        pytest.param(51.2194, 4.4025, False, id="antwerp"),
        pytest.param(50.7753, 6.0839, False, id="aachen"),
    ],
)
def test_netherlands(latitude: float, longitude: float, expected: bool) -> None:
    """Test the shipped Netherlands region against real places."""
    region = load_region(available_regions()["NL"])
    assert region.contains(latitude, longitude) is expected
