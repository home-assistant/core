"""Tests for Tomorrow.io const."""
import pytest

from homeassistant.components.tomorrowio.const import TomorrowioSensorEntityDescription
from homeassistant.const import TEMP_FAHRENHEIT


async def test_post_init():
    """Test post initiailization check for TomorrowioSensorEntityDescription."""

    with pytest.raises(RuntimeError):
        TomorrowioSensorEntityDescription(
            key="a", name="b", unit_imperial=TEMP_FAHRENHEIT
        )
