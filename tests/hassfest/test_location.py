"""Tests for hassfest location validation."""

import json
from pathlib import Path

import pytest

from script.hassfest import location
from script.hassfest.model import Config

from . import get_integration

REGION = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
            },
        }
    ],
}


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Return a hassfest config with a region directory."""
    regions_path = tmp_path / location.REGIONS_PATH
    regions_path.mkdir(parents=True)
    (regions_path / "NL.geojson").write_text(json.dumps(REGION))
    return Config(
        root=tmp_path,
        specific_integrations=None,
        action="validate",
        requirements=False,
    )


def test_valid(config: Config) -> None:
    """Test integrations using a shipped region."""
    integration = get_integration("test", config)
    integration.manifest["locations"] = ["NL"]

    content = location.generate_and_validate({"test": integration}, config)

    assert integration.errors == []
    assert config.errors == []
    assert '"NL": [\n        "test",\n    ],' in content


def test_unknown_region(config: Config) -> None:
    """Test integrations using a region that is not shipped."""
    integration = get_integration("test", config)
    integration.manifest["locations"] = ["NL", "XX"]

    location.generate_and_validate({"test": integration}, config)

    assert [error.error for error in integration.errors] == [
        "Unknown region XX, add homeassistant/components/location/regions/XX.geojson"
    ]


def test_invalid_and_unused_regions(config: Config) -> None:
    """Test region files that are invalid or not used by any integration."""
    regions_path = config.root / location.REGIONS_PATH
    (regions_path / "BE.geojson").write_text(json.dumps(REGION))
    (regions_path / "DE.geojson").write_text('{"type": "Point"}')
    integration = get_integration("test", config)
    integration.manifest["locations"] = ["NL", "DE"]

    location.generate_and_validate({"test": integration}, config)

    assert [error.error for error in config.errors] == [
        "Region BE is not used by any integration",
        "Invalid region DE: Unsupported GeoJSON type Point",
    ]
