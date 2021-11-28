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


@dataclass
class StateData(DistrictData):
    """State representation class."""

    hospitalizationCasesBaby: Optional[int]
    hospitalizationIncidenceBaby: Optional[float]
    hospitalizationCasesChildren: Optional[int]
    hospitalizationIncidenceChildren: Optional[float]
    hospitalizationCasesTeen: Optional[int]
    hospitalizationIncidenceTeen: Optional[float]
    hospitalizationCasesGrown: Optional[int]
    hospitalizationIncidenceGrown: Optional[float]
    hospitalizationCasesSenior: Optional[int]
    hospitalizationIncidenceSenior: Optional[float]
    hospitalizationCasesOld: Optional[int]
    hospitalizationIncidenceOld: Optional[float]
