"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from unittest.mock import Mock

from homeassistant.components.camera.const import DATA_CAMERA_PREFS, PREF_PRELOAD_STREAM

EMPTY_8_6_JPEG = b"empty_8_6"
WEBRTC_ANSWER = "a=sendonly"


def mock_camera_prefs(hass, entity_id, prefs=None):
    """Fixture for cloud component."""
    prefs_to_set = {PREF_PRELOAD_STREAM: True}
    if prefs is not None:
        prefs_to_set.update(prefs)
    hass.data[DATA_CAMERA_PREFS]._prefs[entity_id] = prefs_to_set
    return prefs_to_set


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
    mocked_turbo_jpeg.encode.return_value = EMPTY_8_6_JPEG
    return mocked_turbo_jpeg
