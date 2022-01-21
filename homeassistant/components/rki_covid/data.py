"""Represents a district."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from rki_covid_parser.model.country import Country
from rki_covid_parser.model.district import District
from rki_covid_parser.model.state import State


def accumulate_district(district: District) -> DistrictData:
    """Map district to DistrictData."""
    return DistrictData(
        name=district.name,
        county=district.county,
        state=district.state,
        population=district.population,
        count=district.cases,
        deaths=district.deaths,
        casesPerWeek=district.casesPerWeek,
        recovered=district.recovered,
        weekIncidence=district.weekIncidence,
        casesPer100k=district.casesPer100k,
        newCases=district.newCases,
        newDeaths=district.newDeaths,
        newRecovered=district.newRecovered,
        lastUpdate=district.lastUpdate,
    )


def accumulate_country(country: Country) -> DistrictData:
    """Map country to DistrictData."""
    return DistrictData(
        name="Deutschland",
        county="Deutschland",
        state=None,
        population=country.population,
        count=country.cases,
        deaths=country.deaths,
        casesPerWeek=country.casesPerWeek,
        recovered=country.recovered,
        weekIncidence=country.weekIncidence,
        casesPer100k=country.casesPer100k,
        newCases=country.newCases,
        newDeaths=country.newDeaths,
        newRecovered=country.newRecovered,
        lastUpdate=country.lastUpdate,
    )


def accumulate_state(name: str, state: State) -> StateData:
    """Map state to StateData."""
    return StateData(
        name=name,
        county=name,
        state=None,
        population=state.population,
        count=state.cases,
        deaths=state.deaths,
        casesPerWeek=state.casesPerWeek,
        recovered=state.recovered,
        weekIncidence=state.weekIncidence,
        casesPer100k=state.casesPer100k,
        newCases=state.newCases,
        newDeaths=state.newDeaths,
        newRecovered=state.newRecovered,
        lastUpdate=state.lastUpdate,
        hospitalizationCasesBaby=state.hospitalizationCasesBaby,
        hospitalizationIncidenceBaby=state.hospitalizationIncidenceBaby,
        hospitalizationCasesChildren=state.hospitalizationCasesChildren,
        hospitalizationIncidenceChildren=state.hospitalizationIncidenceChildren,
        hospitalizationCasesTeen=state.hospitalizationCasesTeen,
        hospitalizationIncidenceTeen=state.hospitalizationIncidenceTeen,
        hospitalizationCasesGrown=state.hospitalizationCasesGrown,
        hospitalizationIncidenceGrown=state.hospitalizationIncidenceGrown,
        hospitalizationCasesSenior=state.hospitalizationCasesSenior,
        hospitalizationIncidenceSenior=state.hospitalizationIncidenceSenior,
        hospitalizationCasesOld=state.hospitalizationCasesOld,
        hospitalizationIncidenceOld=state.hospitalizationIncidenceOld,
    )


@dataclass
class DistrictData:
    """District representation class."""

    name: str
    county: str | None
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

    hospitalizationCasesBaby: int | None
    hospitalizationIncidenceBaby: float | None
    hospitalizationCasesChildren: int | None
    hospitalizationIncidenceChildren: float | None
    hospitalizationCasesTeen: int | None
    hospitalizationIncidenceTeen: float | None
    hospitalizationCasesGrown: int | None
    hospitalizationIncidenceGrown: float | None
    hospitalizationCasesSenior: int | None
    hospitalizationIncidenceSenior: float | None
    hospitalizationCasesOld: int | None
    hospitalizationIncidenceOld: float | None
