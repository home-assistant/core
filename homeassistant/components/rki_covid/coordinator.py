"""RKI Covid numbers data coordinator."""

from rki_covid_parser.model.district import District
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from rki_covid_parser.parser import RkiCovidParser, Country, State
import logging
from .const import DOMAIN
from datetime import timedelta
import aiohttp
import asyncio
import async_timeout
from typing import Any
from .data import DistrictData, StateData
from homeassistant.helpers import update_coordinator


_LOGGER = logging.getLogger(__name__)


class RkiCovidDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching RKI covid numbers."""

    parser: RkiCovidParser

    def __init__(self, hass: HomeAssistant):
        """Initialize global data update coordinator."""

        session = async_get_clientsession(hass)
        self.parser = RkiCovidParser(session)

        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(hours=3),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data for each district from rki-covid-parser library."""
        _LOGGER.debug("Fetch data from rki-covid-parser")
        items = {}
        try:
            with async_timeout.timeout(30):
                await self.parser.load_data()
                _LOGGER.debug("Fetch data from rki-covid-parser finished successfully")

                # districts
                for d in self.parser.districts:
                    district = self.parser.districts[d]
                    items[district.county] = self._accumulate_district(district)

                # states
                for s in self.parser.states:
                    state = self.parser.states[s]
                    name = "BL " + state.name
                    items[name] = self._accumulate_state(name, state)

                # country
                items["Deutschland"] = self._accumulate_country(self.parser.country)

                _LOGGER.debug("Parsing data finished")

        except asyncio.TimeoutError as err:
            raise update_coordinator.UpdateFailed(
                f"Error reading data from rki-covid-parser timed-out: {err}"
            )
        except aiohttp.ClientError as err:
            raise update_coordinator.UpdateFailed(
                f"Error reading data from rki-covid-parser by client: {err}"
            )

        return items

    def _accumulate_country(self, country: Country) -> DistrictData:
        return DistrictData(
            "Deutschland",
            "Deutschland",
            None,
            country.population,
            country.cases,
            country.deaths,
            country.casesPerWeek,
            country.recovered,
            country.weekIncidence,
            country.casesPer100k,
            country.newCases,
            country.newDeaths,
            country.newRecovered,
            country.lastUpdate,
        )

    def _accumulate_state(self, name: str, state: State) -> StateData:
        return StateData(
            name,
            name,
            None,
            state.population,
            state.cases,
            state.deaths,
            state.casesPerWeek,
            state.recovered,
            state.weekIncidence,
            state.casesPer100k,
            state.newCases,
            state.newDeaths,
            state.newRecovered,
            state.lastUpdate,
            state.hospitalizationCasesBaby,
            state.hospitalizationIncidenceBaby,
            state.hospitalizationCasesChildren,
            state.hospitalizationIncidenceChildren,
            state.hospitalizationCasesTeen,
            state.hospitalizationIncidenceTeen,
            state.hospitalizationCasesGrown,
            state.hospitalizationIncidenceGrown,
            state.hospitalizationCasesSenior,
            state.hospitalizationIncidenceSenior,
            state.hospitalizationCasesOld,
            state.hospitalizationIncidenceOld,
        )

    def _accumulate_district(self, district: District) -> DistrictData:
        return DistrictData(
            district.name,
            district.county,
            district.state,
            district.population,
            district.cases,
            district.deaths,
            district.casesPerWeek,
            district.recovered,
            district.weekIncidence,
            district.casesPer100k,
            district.newCases,
            district.newDeaths,
            district.newRecovered,
            district.lastUpdate,
        )
