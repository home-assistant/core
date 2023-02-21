"""The Formula 1 integration."""
from __future__ import annotations

from datetime import datetime
import logging

import async_timeout
import ergast_py as ergast
import pytz

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, F1_DISCOVERY_NEW

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Formula 1 from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    f1_data: F1Data = F1Data(hass)
    f1_coordinator: F1UpdateCoordinator = F1UpdateCoordinator(hass, f1_data)
    hass.data[DOMAIN][entry.entry_id] = f1_coordinator

    await f1_coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class F1Data:
    """Hold component state."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the component state."""
        self.hass = hass
        self.ergast = ergast.Ergast()
        self.constructor_standings: list[ergast.ConstructorStanding] = []
        self.driver_standings: list[ergast.DriverStanding] = []
        self.races: list[ergast.Race] = []
        self.races_next_year: list[ergast.Race] = []
        self.season = -1
        self.round = -1
        self.entity_ids: list[str] = []

    async def update(self):
        """Update status from the online service."""
        _LOGGER.info("Updating")

        try:
            constructor_standings = await self.hass.async_add_executor_job(
                self.ergast.season().get_constructor_standings
            )
            driver_standings = await self.hass.async_add_executor_job(
                self.ergast.season().get_driver_standings
            )
            races = await self.hass.async_add_executor_job(
                self.ergast.season().get_races
            )

            current_season = int(races[0].season)
            next_season = current_season + 1

            races_next_year = await self.hass.async_add_executor_job(
                self.ergast.season(next_season).get_races
            )

        except Exception as ex:
            raise UpdateFailed(ex) from ex

        if (
            len(constructor_standings) != 1
            or len(driver_standings) != 1
            or len(races) < 1
        ):
            raise UpdateFailed

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

    def all_constructor_positions(self) -> set[int]:
        """Gather all constructor positions."""
        ret: set[int] = set()

        for standing in self.constructor_standings:
            ret.add(standing.position)

        return ret

    def all_constructor_ids(self) -> set[str]:
        """Gather all constructor ids."""
        ret: set[str] = set()

        for standing in self.constructor_standings:
            ret.add(standing.constructor.constructor_id)

        return ret

    def all_driver_positions(self) -> set[int]:
        """Gather all driver positions."""
        ret: set[int] = set()

        for standing in self.driver_standings:
            ret.add(standing.position)

        return ret

    def all_driver_ids(self) -> set[str]:
        """Gather all driver ids."""
        ret: set[str] = set()

        for standing in self.driver_standings:
            ret.add(standing.driver.driver_id)

        return ret

    def count_race_rounds(self) -> int:
        """Count the number of races."""
        return len(self.races)

    def get_driver_name(self, driver_id: str) -> str | None:
        """Get the formatted name of the Driver."""
        standing = self.get_driver_standing_by_id(driver_id)

        if standing is None:
            return None

        return standing.driver.given_name + " " + standing.driver.family_name

    def new_sensors_discovered(
        self,
        new_constructor_standings: list[ergast.ConstructorStanding],
        new_driver_standings: list[ergast.DriverStanding],
        new_races: list[ergast.Race],
    ) -> bool:
        """Determine if there are any new constructors/drivers/races."""
        cur_constructor_positions = self.all_constructor_positions()
        cur_constructor_ids = self.all_constructor_ids()
        cur_driver_positions = self.all_driver_positions()
        cur_driver_ids = self.all_driver_ids()
        cur_race_count = self.count_race_rounds()

        for new_standing in new_constructor_standings:
            if (
                new_standing.position not in cur_constructor_positions
                or new_standing.constructor.constructor_id not in cur_constructor_ids
            ):
                return True

        for new_standing in new_driver_standings:
            if (
                new_standing.position not in cur_driver_positions
                or new_standing.driver.driver_id not in cur_driver_ids
            ):
                return True

        if len(new_races) != cur_race_count:
            return True

        return False

    def get_constructor_standing_by_id(
        self, constructor_id: str
    ) -> ergast.ConstructorStanding | None:
        """Get ConstructorStanding for a constructor_id."""
        for standing in self.constructor_standings:
            if standing.constructor.constructor_id == constructor_id:
                return standing

        return None

    def get_constructor_standing_by_position(
        self, position: int
    ) -> ergast.ConstructorStanding | None:
        """Get ConstructorStanding for a position."""
        for standing in self.constructor_standings:
            if standing.position == position:
                return standing

        return None

    def get_driver_standing_by_id(self, driver_id: str) -> ergast.DriverStanding | None:
        """Get DriverStanding for a driver_id."""
        for standing in self.driver_standings:
            if standing.driver.driver_id == driver_id:
                return standing

        return None

    def get_driver_standing_by_position(
        self, position: int
    ) -> ergast.DriverStanding | None:
        """Get DriverStanding for a position."""
        for standing in self.driver_standings:
            if standing.position == position:
                return standing

        return None

    def get_race_by_round(self, round_no: int) -> ergast.Race | None:
        """Get Race for round."""
        for race in self.races:
            if race.round_no == round_no:
                return race

        return None

    def get_next_race(self) -> ergast.Race | None:
        """Get the next Race."""
        now = datetime.utcnow().replace(tzinfo=pytz.UTC)

        for race in self.races:
            race_date = race.date.replace(tzinfo=pytz.UTC)
            if race_date > now:
                return race

        for race in self.races_next_year:
            race_date = race.date.replace(tzinfo=pytz.UTC)
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


class F1UpdateCoordinator(DataUpdateCoordinator):
    """Formula 1 coordinator."""

    def __init__(self, hass: HomeAssistant, f1_data: F1Data) -> None:
        """Initialize the data update coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

        self.f1_data = f1_data

    async def _async_update_data(self):
        """Fetch data from API endpoint."""

        async with async_timeout.timeout(60):
            await self.f1_data.update()
