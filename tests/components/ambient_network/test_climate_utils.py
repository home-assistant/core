"""Test the Ambient Weather Network climate utilities."""

from homeassistant.components.ambient_network.climate_utils import ClimateUtils


def test_dew_point() -> None:
    """Test dew point temperature."""

    assert ClimateUtils.dew_point_fahrenheit(None, None) is None
    assert ClimateUtils.dew_point_fahrenheit(50.0, 70.0) == 40.60648803127103
    assert ClimateUtils.dew_point_celsius(10.0, 70.0) == 4.781382239595014


def test_feels_like() -> None:
    """Test feels like temperature."""

    assert ClimateUtils.feels_like_fahrenheit(None, None, None) is None
    assert ClimateUtils.feels_like_fahrenheit(50.0, 70.0, 10.0) == 50.0
    assert ClimateUtils.feels_like_fahrenheit(40.0, 70.0, 10.0) == 33.64254827558847
    assert ClimateUtils.feels_like_fahrenheit(90.0, 70.0, 10.0) == 105.92202060000027
    assert ClimateUtils.feels_like_fahrenheit(90.0, 10.0, 10.0) == 85.27896836218746
    assert ClimateUtils.feels_like_fahrenheit(80.0, 90.0, 10.0) == 86.34189169999989
    assert ClimateUtils.feels_like_celsius(None, None, None) is None
    assert ClimateUtils.feels_like_celsius(26.6667, 90.0, 16.0934) == 30.190028154626237
