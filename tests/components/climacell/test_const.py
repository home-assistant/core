"""Tests for ClimaCell const."""
import pytest

from homeassistant.components.climacell.const import ClimaCellSensorEntityDescription
from homeassistant.const import TEMP_FAHRENHEIT


async def test_post_init():
    """Test post initialization check for ClimaCellSensorEntityDescription."""

    with pytest.raises(RuntimeError):
        ClimaCellSensorEntityDescription(
            key="a", name="b", unit_imperial=TEMP_FAHRENHEIT
        )
