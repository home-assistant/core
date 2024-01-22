"""Tests for the CO2 Signal integration."""
from aioelectricitymaps.models import (
    CarbonIntensityData,
    CarbonIntensityResponse,
    CarbonIntensityUnit,
)

VALID_RESPONSE = CarbonIntensityResponse(
    status="ok",
    country_code="FR",
    data=CarbonIntensityData(
        carbon_intensity=45.98623190095805,
        fossil_fuel_percentage=5.461182741937103,
    ),
    units=CarbonIntensityUnit(
        carbon_intensity="gCO2eq/kWh",
    ),
)
