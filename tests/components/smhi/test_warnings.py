"""Testing the functionality of the SmhiWarnings class."""

from unittest.mock import patch

import pytest

from homeassistant.components.smhi.smhi_geolocation_event import SmhiGeolocationEvent
from homeassistant.components.smhi.warnings import SmhiWarnings


@pytest.fixture
def smhi_warnings():
    """Fixture to create an instance of SmhiWarnings class.

    Returns:
        SmhiWarnings: An instance of the SmhiWarnings class.
    """
    return SmhiWarnings()


@pytest.fixture
def fake_warning_data():
    """Mock the warnings data."""
    return [
        {
            "id": 1734,
            "normalProbability": True,
            "event": {"en": "High water discharge", "code": "HIGH_FLOW"},
            "descriptions": [],
            "warningAreas": [
                {
                    "id": 4926,
                    "approximateStart": "2023-11-05T23:00:00.000Z",
                    "approximateEnd": "2023-11-22T00:00:00.000Z",
                    "published": "2023-11-21T09:35:19.673Z",
                    "normalProbability": True,
                    "areaName": {"en": "The coastal area of Gävleborgs län"},
                    "warningLevel": {"code": "YELLOW"},
                    "eventDescription": {"en": "High water discharge"},
                    "affectedAreas": [{"id": 21, "en": "Gävleborg County"}],
                    "descriptions": [
                        {
                            "title": {"en": "Description of incident"},
                            "text": {"en": "Recent snowmelt combined with rainfall..."},
                        },
                        # ... other descriptions ...
                    ],
                    "area": {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [
                                        [
                                            [17.301084, 60.750685],
                                            # ... other coordinates ...
                                        ]
                                    ],
                                },
                            }
                        ],
                    },
                }
            ],
        }
    ]


async def test_get_warnings(smhi_warnings, fake_warning_data):
    """Test the get_warnings method of the SmhiWarnings class."""
    with patch(
        "homeassistant.components.smhi.downloader.SmhiDownloader.download_json",
        return_value=fake_warning_data,
    ):
        result = await smhi_warnings.get_warnings()
        assert isinstance(result, list)
        assert isinstance(result[0], SmhiGeolocationEvent)
        assert len(result) > 0


def test_parse_warnings(smhi_warnings, fake_warning_data):
    """Test the parse_warnings method of the SmhiWarnings class."""
    result = smhi_warnings.parse_warnings(fake_warning_data)
    assert isinstance(result, list)
    assert len(result) > 0
    assert isinstance(result[0], SmhiGeolocationEvent)


def test_parse_individual_warning(smhi_warnings, fake_warning_data):
    """Test the parse_individual_warning method of SmhiWarnings."""
    warning = fake_warning_data[0]
    parsed_warning = smhi_warnings.parse_individual_warning(warning)
    assert parsed_warning["id"] == warning["id"]
    assert parsed_warning["normalProbability"] == warning["normalProbability"]
    assert "warningAreas" in parsed_warning


def test_parse_warning_area(smhi_warnings, fake_warning_data):
    """Test the parse_warning_area method of SmhiWarnings."""
    area = fake_warning_data[0]["warningAreas"][0]
    parsed_area = smhi_warnings.parse_warning_area(area)
    assert parsed_area["id"] == area["id"]
    assert parsed_area["approximateStart"] == area["approximateStart"]
    assert "geometry" in parsed_area


def test_create_geo_entities_from_warning(smhi_warnings, fake_warning_data):
    """Test the create_geo_entities_from_warning method of SmhiWarnings."""
    warning = smhi_warnings.parse_individual_warning(fake_warning_data[0])
    entities = smhi_warnings.create_geo_entities_from_warning(warning)
    assert isinstance(entities, list)
    assert len(entities) > 0
    assert isinstance(entities[0], SmhiGeolocationEvent)
