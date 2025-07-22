"""Test for NOAA Tides helpers."""

from homeassistant.components.noaa_tides.helpers import get_default_unit_system
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import METRIC_SYSTEM


async def test_get_default_unit_system_english(hass: HomeAssistant) -> None:
    """Test get default unit system."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    result = get_default_unit_system(hass)
    assert result == "english"


async def test_get_default_unit_system_metric(hass: HomeAssistant) -> None:
    """Test get default unit system."""
    hass.config.units = METRIC_SYSTEM
    result = get_default_unit_system(hass)
    assert result == "metric"
