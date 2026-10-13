"""Region polygons stored as GeoJSON and point-in-polygon matching."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

REGIONS_PATH = Path(__file__).parent / "regions"
REGION_FILE_SUFFIX = ".geojson"

type _Ring = tuple[tuple[float, float], ...]


@dataclass(slots=True, frozen=True)
class _Polygon:
    """Polygon with optional holes, positions in (longitude, latitude) order."""

    rings: tuple[_Ring, ...]
    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float

    def contains(self, latitude: float, longitude: float) -> bool:
        """Return if the polygon contains the coordinates."""
        if not (
            self.min_longitude <= longitude <= self.max_longitude
            and self.min_latitude <= latitude <= self.max_latitude
        ):
            return False
        # Even-odd rule over all rings, so a point inside a hole is outside
        inside = False
        for ring in self.rings:
            if _ring_contains(ring, latitude, longitude):
                inside = not inside
        return inside


def _ring_contains(ring: _Ring, latitude: float, longitude: float) -> bool:
    """Return if a ray cast from the coordinates crosses the ring an odd number of times."""
    inside = False
    prev_lon, prev_lat = ring[-1]
    for lon, lat in ring:
        if (lat > latitude) != (prev_lat > latitude) and longitude < (
            prev_lon - lon
        ) * (latitude - lat) / (prev_lat - lat) + lon:
            inside = not inside
        prev_lon, prev_lat = lon, lat
    return inside


class Region:
    """Area made up of one or more polygons."""

    def __init__(self, polygons: Iterable[_Polygon]) -> None:
        """Initialize the region."""
        self._polygons = tuple(polygons)

    def contains(self, latitude: float, longitude: float) -> bool:
        """Return if the region contains the coordinates."""
        return any(polygon.contains(latitude, longitude) for polygon in self._polygons)


def parse_region(data: Any) -> Region:
    """Parse a GeoJSON object into a region.

    Accepts a FeatureCollection, Feature, Polygon or MultiPolygon.
    Raises ValueError if the object is not valid.
    """
    if not (polygons := [_parse_polygon(rings) for rings in _iter_polygons(data)]):
        raise ValueError("No polygons found")
    return Region(polygons)


def load_region(path: Path) -> Region:
    """Load a region from a GeoJSON file."""
    return parse_region(json.loads(path.read_text(encoding="utf-8")))


def available_regions() -> dict[str, Path]:
    """Return the region files shipped with Home Assistant, keyed by region id."""
    return {path.stem: path for path in REGIONS_PATH.glob(f"*{REGION_FILE_SUFFIX}")}


def match_regions(
    region_paths: dict[str, Path], latitude: float, longitude: float
) -> set[str]:
    """Return the ids of the regions that contain the coordinates."""
    return {
        region_id
        for region_id, path in region_paths.items()
        if load_region(path).contains(latitude, longitude)
    }


def _iter_polygons(data: Any) -> Iterator[Any]:
    """Yield the coordinates of every polygon in a GeoJSON object."""
    match data:
        case {"type": "FeatureCollection", "features": list() as features}:
            for feature in features:
                yield from _iter_polygons(feature)
        case {"type": "Feature", "geometry": geometry}:
            yield from _iter_polygons(geometry)
        case {"type": "Polygon", "coordinates": list() as rings}:
            yield rings
        case {"type": "MultiPolygon", "coordinates": list() as polygons}:
            yield from polygons
        case {"type": str() as geojson_type}:
            raise ValueError(f"Unsupported GeoJSON type {geojson_type}")
        case _:
            raise ValueError("Invalid GeoJSON object")


def _parse_polygon(rings: Any) -> _Polygon:
    """Parse and validate the coordinates of a GeoJSON polygon."""
    if not isinstance(rings, list) or not rings:
        raise ValueError("Polygon must have at least one ring")
    parsed = tuple(_parse_ring(ring) for ring in rings)
    exterior = parsed[0]
    return _Polygon(
        rings=parsed,
        min_longitude=min(lon for lon, _ in exterior),
        min_latitude=min(lat for _, lat in exterior),
        max_longitude=max(lon for lon, _ in exterior),
        max_latitude=max(lat for _, lat in exterior),
    )


def _parse_ring(ring: Any) -> _Ring:
    """Parse and validate a GeoJSON linear ring."""
    if not isinstance(ring, list) or len(ring) < 4:
        raise ValueError("Linear ring must have at least four positions")
    parsed = tuple(_parse_position(position) for position in ring)
    if parsed[0] != parsed[-1]:
        raise ValueError("Linear ring must be closed")
    return parsed


def _parse_position(position: Any) -> tuple[float, float]:
    """Parse and validate a GeoJSON position, ignoring the altitude."""
    match position:
        case [int() | float() as lon, int() | float() as lat, *_] if (
            -180 <= lon <= 180 and -90 <= lat <= 90
        ):
            return float(lon), float(lat)
    raise ValueError(f"Invalid position {position}")
