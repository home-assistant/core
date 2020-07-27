"""Collection of fixtures and functions for the HomeKit tests."""
from tests.async_mock import Mock, patch

EMPTY_8_6_JPEG = b"empty_8_6"


def patch_debounce():
    """Return patch for debounce method."""
    return patch(
        "homeassistant.components.homekit.accessories.debounce",
        lambda f: lambda *args, **kwargs: f(*args, **kwargs),
    )


def mock_turbo_jpeg(
    first_width=None, second_width=None, first_height=None, second_height=None
):
    """Mock a TurboJPEG instance."""
    mocked_turbo_jpeg = Mock()
    mocked_turbo_jpeg.decode_header.side_effect = [
        (first_width, first_height, 0, 0),
        (second_width, second_height, 0, 0),
    ]
    mocked_turbo_jpeg.scale_with_quality.return_value = EMPTY_8_6_JPEG
    return mocked_turbo_jpeg
