"""Fixtures for cover entity components tests."""

import pytest

from homeassistant.components.cover import CoverEntityFeature

from .common import MockCover


@pytest.fixture
def mock_cover_entities() -> list[MockCover]:
    """Return a list of MockCover instances."""
    return [
        MockCover(
            name="Simple cover",
            unique_id="unique_cover",
            supported_features=CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
        ),
        MockCover(
            name="Set position cover",
            unique_id="unique_set_pos_cover",
            current_cover_position=50,
            supported_features=CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION,
        ),
        MockCover(
            name="Simple tilt cover",
            unique_id="unique_tilt_cover",
            supported_features=CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT,
        ),
        MockCover(
            name="Set tilt position cover",
            unique_id="unique_set_pos_tilt_cover",
            current_cover_tilt_position=50,
            supported_features=CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
        ),
        MockCover(
            name="All functions cover",
            unique_id="unique_all_functions_cover",
            current_cover_position=50,
            current_cover_tilt_position=50,
            supported_features=CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
        ),
        MockCover(
            name="Simple with opening/closing cover",
            unique_id="unique_opening_closing_cover",
            supported_features=CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
            reports_opening_closing=True,
        ),
    ]
