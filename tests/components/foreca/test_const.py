"""Test the Foreca weather symbol mapping."""

import pytest

from homeassistant.components.foreca.const import symbol_to_condition
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
)


@pytest.mark.parametrize(
    ("code", "condition"),
    [
        pytest.param("d000", ATTR_CONDITION_SUNNY, id="clear_day"),
        pytest.param("d100", ATTR_CONDITION_SUNNY, id="almost_clear_day"),
        pytest.param("n000", ATTR_CONDITION_CLEAR_NIGHT, id="clear_night"),
        pytest.param("n100", ATTR_CONDITION_CLEAR_NIGHT, id="almost_clear_night"),
        pytest.param("d200", ATTR_CONDITION_PARTLYCLOUDY, id="half_cloudy"),
        pytest.param("d300", ATTR_CONDITION_PARTLYCLOUDY, id="broken"),
        pytest.param("d400", ATTR_CONDITION_CLOUDY, id="overcast"),
        pytest.param("d500", ATTR_CONDITION_PARTLYCLOUDY, id="thin_high_clouds"),
        pytest.param("d600", ATTR_CONDITION_FOG, id="fog_day"),
        pytest.param("n600", ATTR_CONDITION_FOG, id="fog_night"),
        pytest.param("d210", ATTR_CONDITION_RAINY, id="slight_rain"),
        pytest.param("d320", ATTR_CONDITION_RAINY, id="rain_showers"),
        pytest.param("d430", ATTR_CONDITION_POURING, id="continuous_rain"),
        pytest.param("d211", ATTR_CONDITION_SNOWY_RAINY, id="sleet"),
        pytest.param("d212", ATTR_CONDITION_SNOWY, id="slight_snow"),
        pytest.param("d422", ATTR_CONDITION_SNOWY, id="snow_showers"),
        pytest.param("d240", ATTR_CONDITION_LIGHTNING_RAINY, id="thunder_rain"),
        pytest.param("d442", ATTR_CONDITION_SNOWY, id="thunder_snow"),
        pytest.param(None, None, id="missing"),
        pytest.param("", None, id="empty"),
        pytest.param("bogus", None, id="unparseable"),
        pytest.param("x421", None, id="bad_day_night_prefix"),
    ],
)
def test_symbol_to_condition(code: str | None, condition: str | None) -> None:
    """Test Foreca symbol codes map to Home Assistant conditions."""
    assert symbol_to_condition(code) == condition
