"""Lightning test class."""
from unittest.mock import patch

import pytest

from homeassistant.components.smhi.lightning_api import SmhiLightning
from homeassistant.components.smhi.smhi_geolocation_event import SmhiGeolocationEvent


@pytest.fixture
def smhi_lightning():
    """Fixture to create an instance of the SmhiLightning class.

    Returns:
        SmhiLightning: An instange of the SmhiLightning class.
    """
    return SmhiLightning()


@pytest.fixture
def fake_lightning_data():
    """Mock lightning data."""
    return {
        "values": [
            {
                # ... other values not used by SmhiLightning ...
                "hours": 15,
                "minutes": 15,
                "seconds": 15,
                "lat": 56.2043,
                "lon": 12.4787,
                "peakCurrent": -5
                # ... other values not used by SmhiLightning ...
            }
            # ... more lightning impacts ...
        ]
    }


async def test_get_lightning_data(smhi_lightning, fake_lightning_data):
    """Test the get_lightning_impacts method of the SmhiLightning class."""
    with patch(
        "homeassistant.components.smhi.downloader.SmhiDownloader.download_json",
        return_value=fake_lightning_data,
    ):
        result = await smhi_lightning.get_lightning_impacts()
        assert isinstance(result, list)  # Check that result is of correct type.
        assert len(result) > 0  # Check that result is not empty.
        assert isinstance(
            result[0], SmhiGeolocationEvent
        )  # Check that element of result is correct type.


def test_parse_lightning(smhi_lightning, fake_lightning_data):
    """Test the parse_lightning_impacts method of SmhiLightning class."""
    result = smhi_lightning.parse_lightning_impacts(fake_lightning_data)
    assert isinstance(result, list)  # Check that result is correct type.
    assert len(result) > 0  # Check that result is not empty.
    assert isinstance(
        result[0], SmhiGeolocationEvent
    )  # Check that element of result is correct type.
