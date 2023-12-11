"""Tests for radar ImageEntity."""
from PIL import Image
import pytest

from homeassistant.components.smhi.image import RadarImage


@pytest.fixture
def radar_image_content():
    """Fixture providing the content of a radar image."""
    with open("tests/components/smhi/test_images/radar.png", "rb") as radar_file:
        return radar_file.read()


@pytest.fixture
def map_image_content():
    """Fixture providing the content of a map image."""
    with open("tests/components/smhi/test_images/basemap.png", "rb") as map_file:
        return map_file.read()


def test_combine_radar_images(radar_image_content, map_image_content):
    """Test the combine_radar_images function."""
    result_image = RadarImage.combine_radar_images(
        radar_image_content, map_image_content
    )

    # Check if the result is an instance of the Image class
    assert isinstance(result_image, Image.Image)

    # Check the dimensions of the result image
    expected_dimensions = (471, 887)  # The exact dimensions for radar images from SMHI
    assert result_image.size == expected_dimensions
