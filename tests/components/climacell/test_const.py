"""Tests for ClimaCell const."""
import pytest

from homeassistant.components.climacell.const import ClimaCellSensorMetadata
from homeassistant.const import TEMP_FAHRENHEIT


async def test_post_init():
    """Test post initiailization check for ClimaCellSensorMetadata."""

    with pytest.raises(RuntimeError):
        ClimaCellSensorMetadata("a", "b", unit_imperial=TEMP_FAHRENHEIT)
