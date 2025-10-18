"""Test Roborock Sensors."""

import pytest
from roborock.const import (
    CLEANING_BRUSH_REPLACE_TIME,
    FILTER_REPLACE_TIME,
    MAIN_BRUSH_REPLACE_TIME,
    SENSOR_DIRTY_REPLACE_TIME,
    SIDE_BRUSH_REPLACE_TIME,
    STRAINER_REPLACE_TIME,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SENSOR]


async def test_sensors(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors and check test values are correctly set."""
    assert snapshot == hass.states.async_all("sensor")
