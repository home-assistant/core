"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.camera.const import DATA_CAMERA_PREFS, PREF_PRELOAD_STREAM


def mock_camera_prefs(hass, entity_id, prefs=None):
    """Fixture for cloud component."""
    prefs_to_set = {PREF_PRELOAD_STREAM: True}
    if prefs is not None:
        prefs_to_set.update(prefs)
    hass.data[DATA_CAMERA_PREFS]._prefs[entity_id] = prefs_to_set
    return prefs_to_set
