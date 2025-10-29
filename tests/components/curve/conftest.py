"""Fixtures for Curve tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.curve.const import CONF_SEGMENTS, CONF_SOURCE, DOMAIN
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry

MOCK_SEGMENTS = [
    {"x0": 0, "y0": 0, "x1": 10, "y1": 5},
    {"x0": 10, "y0": 5, "x1": 20, "y1": 15},
]

MOCK_STEP_SEGMENTS = [
    {"x0": 0, "y0": 0, "x1": 10, "y1": 5, "type": "step"},
    {"x0": 10, "y0": 5, "x1": 20, "y1": 15, "type": "step"},
]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Curve",
        options={
            CONF_NAME: "Test Curve",
            CONF_SOURCE: "sensor.test_source",
            CONF_SEGMENTS: MOCK_SEGMENTS,
        },
        unique_id="test_curve_unique_id",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.curve.async_setup_entry", return_value=True):
        yield
