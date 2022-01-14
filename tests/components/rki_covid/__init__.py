"""Tests for RKI Covid numbers sensor."""

from rki_covid_parser.model.district import District
from rki_covid_parser.model.state import State
from rki_covid_parser.model.country import Country

MOCK_DISTRICTS = {
    "1": District(
        {
            "RS": "01234",
            "GEN": "Amberg",
            "county": "SK Amberg",
            "BL": "Bayern",
            "EWZ": 45678,
            "cases": 12345,
            "deaths": 23456,
            "cases7_lk": 34567,
            "death7_lk": 45678,
            "last_update": "01.01.2022, 00:00 Uhr",
        }
    ),
}

MOCK_STATE = State("Bayern")
MOCK_STATE.population = 99
MOCK_STATE.cases = 88
MOCK_STATE.deaths = 77
MOCK_STATE.casesPerWeek = 66
MOCK_STATE.recovered = 55
MOCK_STATE.deathsPerWeek = 44
MOCK_STATE.newCases = 33
MOCK_STATE.newDeaths = 22
MOCK_STATE.newRecovered = 11

MOCK_STATE.hospitalizationCasesBaby = 9.8
MOCK_STATE.id = 4
MOCK_STATE.name = "Bayern"
MOCK_STATE.vaccinationTotal = 20
MOCK_STATE.vaccinationFirst = 30
MOCK_STATE.vaccinationFull = 40
MOCK_STATE.hospitalizationCasesMerged = 50.1
MOCK_STATE.hospitalizationIncidenceMerged = 60.2
MOCK_STATE.hospitalizationCasesBaby = 70.3
MOCK_STATE.hospitalizationIncidenceBaby = 80.3
MOCK_STATE.hospitalizationCasesChildren = 90.3
MOCK_STATE.hospitalizationIncidenceChildren = 100.3
MOCK_STATE.hospitalizationCasesTeen = 101.1
MOCK_STATE.hospitalizationIncidenceTeen = 102.2
MOCK_STATE.hospitalizationCasesGrown = 103.3
MOCK_STATE.hospitalizationIncidenceGrown = 104.4
MOCK_STATE.hospitalizationCasesSenior = 105.5
MOCK_STATE.hospitalizationIncidenceSenior = 106.6
MOCK_STATE.hospitalizationCasesOld = 107.7
MOCK_STATE.hospitalizationIncidenceOld = 108.8
MOCK_STATE.lastUpdate = "01.01.2022, 00:00 Uhr"


MOCK_STATES = {"Bayern": MOCK_STATE}

MOCK_COUNTRY = Country()
MOCK_COUNTRY.id = "Deutschland"
MOCK_COUNTRY.name = "Deutschland"
MOCK_COUNTRY.lastUpdate = "01.01.2022, 00:00 Uhr"
MOCK_COUNTRY.population = 83129285
MOCK_COUNTRY.cases = 7835451
MOCK_COUNTRY.deaths = 115337
MOCK_COUNTRY.casesPerWeek = 94227
MOCK_COUNTRY.deathsPerWeek = 8
MOCK_COUNTRY.recovered = 6914679
MOCK_COUNTRY.newCases = 192
MOCK_COUNTRY.newDeaths = 386
MOCK_COUNTRY.newRecovered = 182
