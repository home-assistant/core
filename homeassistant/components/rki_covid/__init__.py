"""RKI Covid numbers integration."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import async_timeout
from rki_covid_parser.parser import RkiCovidParser

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, update_coordinator

from .const import DOMAIN
from .data import DistrictData, StateData

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the component into HomeAssistant."""
    _LOGGER.debug("setup component.")
    parser = RkiCovidParser(aiohttp_client.async_get_clientsession(hass))

    # Make sure coordinator is initialized.
    await get_coordinator(hass, parser)

    # Return boolean to indicate that initialization was successful.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up component from a config entry."""
    _LOGGER.debug(f"Setup item from config entry: {entry.data}.")
    # Forward the setup to the sensor platform.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def get_coordinator(hass: HomeAssistant, parser: RkiCovidParser):
    """Get the data update coordinator."""
    _LOGGER.debug("initialize the data coordinator.")
    if DOMAIN in hass.data:
        return hass.data[DOMAIN]

    async def async_get_districts():
        """Fetch data from rki-covid-parser library.

        Here the data for each district is loaded.
        """
        _LOGGER.debug("fetch data from rki-covid-parser.")
        try:
            with async_timeout.timeout(30):
                # return {case.county: case for case in await api.load_districts()}
                await parser.load_data()
                _LOGGER.debug("fetching finished.")

                items = {}

                # districts
                for d in parser.districts:
                    district = parser.districts[d]

                    items[district.county] = DistrictData(
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

                # states
                for s in parser.states:
                    state = parser.states[s]
                    name = "BL " + state.name
                    items[name] = StateData(
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

                # country
                items["Deutschland"] = DistrictData(
                    "Deutschland",
                    "Deutschland",
                    None,
                    parser.country.population,
                    parser.country.cases,
                    parser.country.deaths,
                    parser.country.casesPerWeek,
                    parser.country.recovered,
                    parser.country.weekIncidence,
                    parser.country.casesPer100k,
                    parser.country.newCases,
                    parser.country.newDeaths,
                    parser.country.newRecovered,
                    parser.country.lastUpdate,
                )

                _LOGGER.debug("parsing data finished.")
                return items

        except asyncio.TimeoutError as err:
            raise update_coordinator.UpdateFailed(
                f"Error reading data from rki-covid-parser timed-out: {err}"
            )
        except aiohttp.ClientError as err:
            raise update_coordinator.UpdateFailed(
                f"Error reading data from rki-covid-parser by client: {err}"
            )

    hass.data[DOMAIN] = update_coordinator.DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_districts,
        update_interval=timedelta(hours=3),
    )
    await hass.data[DOMAIN].async_refresh()
    return hass.data[DOMAIN]
