"""Converters for the World Air Quality Index (WAQI) integration.

This module provides functions to convert between AQI (Air Quality Index) values
and actual pollutant concentrations in their respective units (μg/m³, ppb, ppm).
"""

from typing import Literal, TypedDict


class ScaleDict(TypedDict):
    """Type for scale dictionary."""

    aqi: list[float]
    conc: list[float]


class ScalesType(TypedDict):
    """Type for scales dictionary."""

    pm25: ScaleDict
    pm10: ScaleDict
    o31: ScaleDict
    o38: ScaleDict
    so21: ScaleDict
    so224: ScaleDict
    no2: ScaleDict
    co: ScaleDict


PollutantType = Literal["pm25", "pm10", "o31", "o38", "so21", "so224", "no2", "co"]


def aqi_to_concentration(aqi: float, pollutant: PollutantType) -> float:
    """Convert AQI score to concentration in appropriate units.

    Args:
        aqi: Air Quality Index value (0-500)
        pollutant: One of 'pm25', 'pm10', 'o31', 'o38', 'so21', 'so224', 'no2', 'co'

    Returns:
        Concentration in appropriate units (μg/m³, ppb, or ppm)

    Raises:
        ValueError: If AQI is out of range or pollutant is invalid

    """
    # Scales definition for all pollutants
    scales: ScalesType = {
        "pm25": {  # μg/m³
            "aqi": [0, 50, 100, 150, 200, 300, 400, 500],
            "conc": [0, 12, 35.5, 55.5, 150.5, 250.5, 350.5, 500.5],
        },
        "pm10": {  # μg/m³
            "aqi": [0, 50, 100, 150, 200, 300, 400, 500],
            "conc": [0, 55, 155, 255, 355, 425, 505, 605],
        },
        "o31": {  # ppb (1 hour average)
            "aqi": [0, 50, 100, 150, 200, 300, 400, 500],
            "conc": [0, 54, 125, 165, 205, 405, 505, 605],
        },
        "o38": {  # ppb (8 hours average)
            "aqi": [0, 50, 100, 150, 200, 300],
            "conc": [0, 54, 70, 85, 105, 200],
        },
        "so21": {  # ppb (1 hour average)
            "aqi": [0, 50, 100, 150, 200],
            "conc": [0, 36, 76, 186, 304, 604],
        },
        "so224": {  # ppb (24 hours average)
            "aqi": [200, 300, 400, 500],
            "conc": [304, 605, 805, 1004],
        },
        "no2": {  # ppb
            "aqi": [0, 50, 100, 150, 200, 300, 400, 500],
            "conc": [0, 0.054, 0.101, 0.361, 0.65, 1.25, 1.65, 2.049],
        },
        "co": {  # ppm
            "aqi": [0, 50, 100, 150, 200, 300, 400, 500],
            "conc": [0, 4.5, 9.5, 12.5, 15.5, 30.5, 40.5, 50.5],
        },
    }

    if pollutant not in scales:
        raise ValueError(f"Pollutant must be one of {list(scales.keys())}")

    if aqi < 0 or aqi > 500:
        raise ValueError(f"AQI must be between 0 and 500, not {aqi}")

    scale = scales[pollutant]

    # Find appropriate interval
    for i in range(len(scale["aqi"]) - 1):
        aqi_low = scale["aqi"][i]
        aqi_high = scale["aqi"][i + 1]

        if aqi_low <= aqi <= aqi_high:
            conc_low = scale["conc"][i]
            conc_high = scale["conc"][i + 1]

            # Inverse AQI conversion formula
            concentration = conc_low + (aqi - aqi_low) * (conc_high - conc_low) / (
                aqi_high - aqi_low
            )
            return round(concentration, 3)

    raise ValueError(
        f"Could not find concentration for AQI {aqi} and pollutant {pollutant}"
    )
