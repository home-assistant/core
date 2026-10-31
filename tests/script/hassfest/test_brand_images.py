"""Tests for the brand image validation in Core."""

from hassfest import brand_images

from homeassistant.components.brands import ALLOWED_IMAGES, IMAGE_FALLBACKS


def test_constants_match_brands_integration() -> None:
    """Test the package validates the same images and fallbacks as the brands view."""
    assert brand_images.ALLOWED_IMAGES == ALLOWED_IMAGES
    assert brand_images.IMAGE_FALLBACKS == IMAGE_FALLBACKS
