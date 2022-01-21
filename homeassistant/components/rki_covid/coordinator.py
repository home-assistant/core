"""RKI Covid numbers data coordinator."""

import asyncio
from datetime import timedelta
import logging

import aiohttp
import async_timeout
from rki_covid_parser.parser import RkiCovidParser

from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .data import accumulate_country, accumulate_district, accumulate_state

_LOGGER = logging.getLogger(__name__)


class RkiCovidDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching RKI covid numbers."""

    parser: RkiCovidParser

    def __init__(self, hass: HomeAssistant) -> None:
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

                # country
                items["Deutschland"] = accumulate_country(self.parser.country)

                # states
                for s in sorted(
                    self.parser.states.values(), key=lambda state: state.name
                ):
                    st = self.parser.states[s.name]
                    name = "BL " + st.name
                    items[name] = accumulate_state(name, st)

                # districts
                for d in sorted(self.parser.districts.values(), key=lambda di: di.name):
                    district = self.parser.districts[d.id]
                    items[district.county] = accumulate_district(district)

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
