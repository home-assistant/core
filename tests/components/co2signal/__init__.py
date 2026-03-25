"""Tests for the CO2 Signal integration."""

from aioelectricitymaps import HomeAssistantCarbonIntensityResponse
from aioelectricitymaps.models.home_assistant import (
    HomeAssistantCarbonIntensityData,
    HomeAssistantCarbonIntensityUnit,
)

VALID_RESPONSE = HomeAssistantCarbonIntensityResponse(
    status="ok",
    country_code="FR",
    data=HomeAssistantCarbonIntensityData(
        carbon_intensity=45.98623190095805,
        fossil_fuel_percentage=5.461182741937103,
    ),
    units=HomeAssistantCarbonIntensityUnit(
        carbon_intensity="gCO2eq/kWh",
    ),
)
