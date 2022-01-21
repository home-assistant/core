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
        cases_per_week=district.casesPerWeek,
        recovered=district.recovered,
        week_incidence=district.weekIncidence,
        cases_per100k=district.casesPer100k,
        new_cases=district.newCases,
        new_deaths=district.newDeaths,
        new_recovered=district.newRecovered,
        last_update=district.lastUpdate,
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
        cases_per_week=country.casesPerWeek,
        recovered=country.recovered,
        week_incidence=country.weekIncidence,
        cases_per100k=country.casesPer100k,
        new_cases=country.newCases,
        new_deaths=country.newDeaths,
        new_recovered=country.newRecovered,
        last_update=country.lastUpdate,
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
        cases_per_week=state.casesPerWeek,
        recovered=state.recovered,
        week_incidence=state.weekIncidence,
        cases_per100k=state.casesPer100k,
        new_cases=state.newCases,
        new_deaths=state.newDeaths,
        new_recovered=state.newRecovered,
        last_update=state.lastUpdate,
        hospitalization_cases_baby=state.hospitalizationCasesBaby,
        hospitalization_incidence_baby=state.hospitalizationIncidenceBaby,
        hospitalization_cases_children=state.hospitalizationCasesChildren,
        hospitalization_incidence_children=state.hospitalizationIncidenceChildren,
        hospitalization_cases_teen=state.hospitalizationCasesTeen,
        hospitalization_incidence_teen=state.hospitalizationIncidenceTeen,
        hospitalization_cases_grown=state.hospitalizationCasesGrown,
        hospitalization_incidence_grown=state.hospitalizationIncidenceGrown,
        hospitalization_cases_senior=state.hospitalizationCasesSenior,
        hospitalization_incidence_senior=state.hospitalizationIncidenceSenior,
        hospitalization_cases_old=state.hospitalizationCasesOld,
        hospitalization_incidence_old=state.hospitalizationIncidenceOld,
    )


@dataclass
class DistrictData:
    """District representation class."""

    name: str
    county: str | None
    state: str | None
    population: str
    count: int
    deaths: int
    cases_per_week: int
    recovered: int
    week_incidence: float
    cases_per100k: float
    new_cases: int
    new_deaths: int
    new_recovered: int
    last_update: datetime


@dataclass
class StateData(DistrictData):
    """State representation class."""

    hospitalization_cases_baby: int | None
    hospitalization_incidence_baby: float | None
    hospitalization_cases_children: int | None
    hospitalization_incidence_children: float | None
    hospitalization_cases_teen: int | None
    hospitalization_incidence_teen: float | None
    hospitalization_cases_grown: int | None
    hospitalization_incidence_grown: float | None
    hospitalization_cases_senior: int | None
    hospitalization_incidence_senior: float | None
    hospitalization_cases_old: int | None
    hospitalization_incidence_old: float | None
