"""The DataUpdateCoordinator for formula_one."""

import asyncio
from datetime import datetime, timezone
from json import JSONDecodeError
import logging

import async_timeout
import ergast_py as ergast
from requests import exceptions as RequestsExceptions

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, F1_DISCOVERY_NEW

_LOGGER = logging.getLogger(__name__)


class F1UpdateCoordinator(DataUpdateCoordinator[None]):
    """Formula 1 coordinator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the data update coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

        self.ergast = ergast.Ergast()
        self.constructor_standings: list[ergast.ConstructorStanding] = []
        self.driver_standings: list[ergast.DriverStanding] = []
        self.races: list[ergast.Race] = []
        self.races_next_year: list[ergast.Race] = []
        self.season = -1
        self.round = -1
        self.entity_ids: list[str] = []

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""

        async with async_timeout.timeout(60):
            await self.update()

    async def update(self):
        """Update status from the online service."""
        _LOGGER.debug("Updating")

        try:
            constructor_standings, driver_standings, races = await asyncio.gather(
                self.hass.async_add_executor_job(
                    self.ergast.season().get_constructor_standings
                ),
                self.hass.async_add_executor_job(
                    self.ergast.season().get_driver_standings
                ),
                self.hass.async_add_executor_job(self.ergast.season().get_races),
            )

            current_season = int(races[0].season)
            next_season = current_season + 1

            races_next_year = await self.hass.async_add_executor_job(
                self.ergast.season(next_season).get_races
            )

        except JSONDecodeError as ex:
            raise UpdateFailed(ex) from ex
        except RequestsExceptions.RequestException as ex:
            raise UpdateFailed(ex) from ex
        except Exception as ex:
            raise UpdateFailed(ex) from ex

        if (
            len(constructor_standings) != 1
            or len(driver_standings) != 1
            or len(races) < 1
        ):
            raise UpdateFailed(
                "The Ergast server returned an unexpected number of results"
            )

        new_sensors_discovered = self.new_sensors_discovered(
            constructor_standings[0].constructor_standings,
            driver_standings[0].driver_standings,
            races,
        )

        self.constructor_standings = constructor_standings[0].constructor_standings
        self.driver_standings = driver_standings[0].driver_standings
        self.races = races
        self.races_next_year = races_next_year
        self.season = constructor_standings[0].season
        self.round = constructor_standings[0].round_no

        if new_sensors_discovered:
            async_dispatcher_send(self.hass, F1_DISCOVERY_NEW)

    def get_driver_name(self, driver_id: str) -> str | None:
        """Get the formatted name of the Driver."""
        for standing in self.driver_standings:
            if standing.driver.driver_id == driver_id:
                return f"{standing.driver.given_name} {standing.driver.family_name}"

        return None

    def new_sensors_discovered(
        self,
        new_constructor_standings: list[ergast.ConstructorStanding],
        new_driver_standings: list[ergast.DriverStanding],
        new_races: list[ergast.Race],
    ) -> bool:
        """Determine if there are any new constructors/drivers/races."""
        cur_constructor_positions = {
            standing.position for standing in self.constructor_standings
        }
        new_constructor_positions = {
            new_standing.position for new_standing in new_constructor_standings
        }
        if len(new_constructor_positions.difference(cur_constructor_positions)) > 0:
            return True

        cur_constructor_ids = {
            standing.constructor.constructor_id
            for standing in self.constructor_standings
        }
        new_constructor_ids = {
            new_standing.constructor.constructor_id
            for new_standing in new_constructor_standings
        }
        if len(new_constructor_ids.difference(cur_constructor_ids)) > 0:
            return True

        cur_driver_positions = {standing.position for standing in self.driver_standings}
        new_driver_positions = {
            new_standing.position for new_standing in new_driver_standings
        }
        if len(new_driver_positions.difference(cur_driver_positions)) > 0:
            return True

        cur_driver_ids = {
            standing.driver.driver_id for standing in self.driver_standings
        }
        new_driver_ids = {
            new_standing.driver.driver_id for new_standing in new_driver_standings
        }
        if len(new_driver_ids.difference(cur_driver_ids)) > 0:
            return True

        if len(new_races) != len(self.races):
            return True

        return False

    def get_race_by_round(self, round_no: int) -> ergast.Race | None:
        """Get Race for round."""
        for race in self.races:
            if race.round_no == round_no:
                return race

        return None

    def get_next_race(self) -> ergast.Race | None:
        """Get the next Race."""
        now = datetime.now(timezone.utc)

        for race in self.races:
            race_date = race.date.replace(tzinfo=timezone.utc)
            if race_date > now:
                return race

        for race in self.races_next_year:
            race_date = race.date.replace(tzinfo=timezone.utc)
            if race_date > now:
                return race

        return None

    async def test_connect(self) -> bool:
        """Test if we can connect with the host."""
        try:
            await self.hass.async_add_executor_job(
                ergast.Ergast().season().get_constructor_standings
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Test connection failed: %s", ex)
            return False

        return True
