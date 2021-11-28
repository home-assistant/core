"""Represents a district."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DistrictData:
    """District representation class."""

    name: str
    county: Optional[str]
    state: str
    population: str
    count: int
    deaths: int
    casesPerWeek: int
    recovered: int
    weekIncidence: float
    casesPer100k: float
    newCases: int
    newDeaths: int
    newRecovered: int
    lastUpdate: datetime
