"""Test the World Air Quality Index (WAQI) converters from AQI."""

import pytest

from homeassistant.components.waqi.converters import aqi_to_concentration


def test_pm25_conversion() -> None:
    """Test PM2.5 AQI to μg/m³ conversion."""
    assert aqi_to_concentration(0, "pm25") == 0
    assert aqi_to_concentration(50, "pm25") == 12.0
    assert aqi_to_concentration(100, "pm25") == 35.5
    assert aqi_to_concentration(200, "pm25") == 150.5
    assert aqi_to_concentration(300, "pm25") == 250.5
    assert aqi_to_concentration(400, "pm25") == 350.5
    assert aqi_to_concentration(500, "pm25") == 500.5


def test_pm10_conversion() -> None:
    """Test PM10 AQI to μg/m³ conversion."""
    assert aqi_to_concentration(0, "pm10") == 0
    assert aqi_to_concentration(50, "pm10") == 55
    assert aqi_to_concentration(100, "pm10") == 155
    assert aqi_to_concentration(150, "pm10") == 255
    assert aqi_to_concentration(200, "pm10") == 355
    assert aqi_to_concentration(300, "pm10") == 425
    assert aqi_to_concentration(400, "pm10") == 505
    assert aqi_to_concentration(500, "pm10") == 605


def test_o3_1h_conversion() -> None:
    """Test O3 (1 hour) AQI to ppb conversion."""
    assert aqi_to_concentration(0, "o31") == 0
    assert aqi_to_concentration(100, "o31") == 0.125
    assert aqi_to_concentration(150, "o31") == 0.165
    assert aqi_to_concentration(200, "o31") == 0.205
    assert aqi_to_concentration(300, "o31") == 0.405
    assert aqi_to_concentration(400, "o31") == 0.505
    assert aqi_to_concentration(500, "o31") == 0.605


def test_o3_8h_conversion() -> None:
    """Test O3 (8 hours) AQI to ppb conversion."""
    assert aqi_to_concentration(0, "o38") == 0
    assert aqi_to_concentration(50, "o38") == 0.06
    assert aqi_to_concentration(100, "o38") == 0.076
    assert aqi_to_concentration(150, "o38") == 0.096
    assert aqi_to_concentration(200, "o38") == 0.116
    assert aqi_to_concentration(300, "o38") == 0.375


def test_so2_1h_conversion() -> None:
    """Test SO2 (1 hour) AQI to ppb conversion."""
    assert aqi_to_concentration(0, "so21") == 0
    assert aqi_to_concentration(50, "so21") == 36
    assert aqi_to_concentration(100, "so21") == 76
    assert aqi_to_concentration(150, "so21") == 186
    assert aqi_to_concentration(200, "so21") == 304


def test_so2_24h_conversion() -> None:
    """Test SO2 (24 hours) AQI to ppb conversion."""
    assert aqi_to_concentration(200, "so224") == 304
    assert aqi_to_concentration(300, "so224") == 605
    assert aqi_to_concentration(400, "so224") == 805
    assert aqi_to_concentration(500, "so224") == 1004


def test_no2_conversion() -> None:
    """Test NO2 AQI to ppb conversion."""
    assert aqi_to_concentration(0, "no2") == 0
    assert aqi_to_concentration(50, "no2") == 0.054
    assert aqi_to_concentration(100, "no2") == 0.101
    assert aqi_to_concentration(150, "no2") == 0.361
    assert aqi_to_concentration(200, "no2") == 0.65
    assert aqi_to_concentration(300, "no2") == 1.25
    assert aqi_to_concentration(400, "no2") == 1.65
    assert aqi_to_concentration(500, "no2") == 2.049


def test_co_conversion() -> None:
    """Test CO AQI to ppm conversion."""
    assert aqi_to_concentration(0, "co") == 0
    assert aqi_to_concentration(50, "co") == 4.5
    assert aqi_to_concentration(100, "co") == 9.5
    assert aqi_to_concentration(150, "co") == 12.5
    assert aqi_to_concentration(200, "co") == 15.5
    assert aqi_to_concentration(300, "co") == 30.5
    assert aqi_to_concentration(400, "co") == 40.5
    assert aqi_to_concentration(500, "co") == 50.5


def test_invalid_pollutant() -> None:
    """Test invalid pollutant raises ValueError."""
    with pytest.raises(ValueError, match="Pollutant must be one of"):
        aqi_to_concentration(50, "invalid")


def test_invalid_aqi() -> None:
    """Test invalid AQI raises ValueError."""
    with pytest.raises(ValueError, match="AQI must be between 0 and 500"):
        aqi_to_concentration(-1, "pm25")
    with pytest.raises(ValueError, match="AQI must be between 0 and 500"):
        aqi_to_concentration(501, "pm25")


def test_intermediate_values() -> None:
    """Test some intermediate AQI values."""
    # PM2.5 at AQI 75 should be between 12 and 35.5 μg/m³
    result = aqi_to_concentration(75, "pm25")
    assert 12 < result < 35.5

    # PM10 at AQI 125 should be between 155 and 255 μg/m³
    result = aqi_to_concentration(125, "pm10")
    assert 155 < result < 255

    # O3 at AQI 175 should be between 0.165 and 0.205 ppb
    result = aqi_to_concentration(175, "o31")
    assert 0.165 < result < 0.205
