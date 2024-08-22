"""Tests for the Assist satellite integration."""

from homeassistant.components import assist_satellite


class MockSatelliteEntity(assist_satellite.AssistSatelliteEntity):
    """Mock satellite that supports pipeline triggering."""

    _attr_supported_features = (
        assist_satellite.AssistSatelliteEntityFeature.TRIGGER_PIPELINE
    )
