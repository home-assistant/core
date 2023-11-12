"""Models to the co2signal integration."""
from typing import TypedDict


class CO2SignalData(TypedDict):
    """Data field."""

    carbonIntensity: float
    fossilFuelPercentage: float


class CO2SignalUnit(TypedDict):
    """Unit field."""

    carbonIntensity: str


class CO2SignalResponse(TypedDict):
    """API response."""

    status: str
    countryCode: str
    data: CO2SignalData
    units: CO2SignalUnit
