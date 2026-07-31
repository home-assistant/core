"""Coordinators for Google Health."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from google_health_api import GoogleHealthApi
from google_health_api.exceptions import (
    GoogleHealthApiError,
    HealthApiForbiddenException,
    HealthAuthException,
)
from google_health_api.model import (
    ActiveEnergyBurnedRollupValue,
    BodyFat,
    DailyRestingHeartRate,
    DistanceRollupValue,
    FloorsRollupValue,
    StepsRollupValue,
    TotalCaloriesRollupValue,
    Weight,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import GoogleHealthConfigEntry

_LOGGER = logging.getLogger(__name__)

POLLING_INTERVAL = timedelta(minutes=15)
BODY_POLLING_INTERVAL = timedelta(hours=1)
DEFAULT_PAGE_SIZE = 1


@dataclass
class GoogleHealthActivityData:
    """Class to hold activity data."""

    steps: StepsRollupValue | None = None
    distance: DistanceRollupValue | None = None
    active_energy_burned: ActiveEnergyBurnedRollupValue | None = None
    total_calories: TotalCaloriesRollupValue | None = None
    floors: FloorsRollupValue | None = None


@dataclass
class GoogleHealthBodyData:
    """Class to hold body measurements."""

    weight: Weight | None = None
    resting_heart_rate: DailyRestingHeartRate | None = None
    body_fat: BodyFat | None = None


class GoogleHealthDataUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base coordinator for Google Health API."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        update_interval: timedelta,
        entry: GoogleHealthConfigEntry,
        api_client: GoogleHealthApi,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api_client
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
            config_entry=entry,
        )

    @override
    async def _async_update_data(self) -> _DataT:
        """Fetch data from API."""
        try:
            return await self._async_fetch_data()
        except (HealthAuthException, HealthApiForbiddenException) as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except GoogleHealthApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err

    async def _async_fetch_data(self) -> _DataT:
        """Fetch data from API."""
        raise NotImplementedError


class GoogleHealthActivityCoordinator(
    GoogleHealthDataUpdateCoordinator[GoogleHealthActivityData]
):
    """Coordinator to fetch activity data from Google Health API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GoogleHealthConfigEntry,
        api_client: GoogleHealthApi,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_activity",
            update_interval=POLLING_INTERVAL,
            entry=entry,
            api_client=api_client,
        )

    @override
    async def _async_fetch_data(self) -> GoogleHealthActivityData:
        """Fetch activity rollups for today.

        Queries the daily rollup endpoints in parallel using Home Assistant's
        local time zone to aggregate steps, distance, active calories, total
        calories, and floors. If no data points exist for today yet, the API
        returns None, which the sensors default to 0.
        """
        (
            steps_rollup,
            distance_rollup,
            active_energy_rollup,
            total_calories_rollup,
            floors_rollup,
        ) = await asyncio.gather(
            self.api.steps.today(self.hass.config.time_zone),
            self.api.distance.today(self.hass.config.time_zone),
            self.api.active_energy_burned.today(self.hass.config.time_zone),
            self.api.total_calories.today(self.hass.config.time_zone),
            self.api.floors.today(self.hass.config.time_zone),
        )

        steps = steps_rollup.data if steps_rollup else None
        distance = distance_rollup.data if distance_rollup else None
        active_energy_burned = (
            active_energy_rollup.data if active_energy_rollup else None
        )
        total_calories = total_calories_rollup.data if total_calories_rollup else None
        floors = floors_rollup.data if floors_rollup else None

        return GoogleHealthActivityData(
            steps=steps,
            distance=distance,
            active_energy_burned=active_energy_burned,
            total_calories=total_calories,
            floors=floors,
        )


class GoogleHealthBodyCoordinator(
    GoogleHealthDataUpdateCoordinator[GoogleHealthBodyData]
):
    """Coordinator to fetch body measurements from Google Health API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GoogleHealthConfigEntry,
        api_client: GoogleHealthApi,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_body",
            update_interval=BODY_POLLING_INTERVAL,
            entry=entry,
            api_client=api_client,
        )

    @override
    async def _async_fetch_data(self) -> GoogleHealthBodyData:
        """Fetch latest body weight, resting heart rate, and body fat in parallel."""
        # The Google Health API returns data points sorted by interval start time
        # in descending order (newest first). Querying with page_size=1 and grabbing
        # the first element is sufficient to fetch the most recent measurement.
        weight_result, hr_result, body_fat_result = await asyncio.gather(
            self.api.weight.list(page_size=DEFAULT_PAGE_SIZE),
            self.api.daily_resting_heart_rate.list(page_size=DEFAULT_PAGE_SIZE),
            self.api.body_fat.list(page_size=DEFAULT_PAGE_SIZE),
        )

        weight = (
            weight_result.data_points[0].data if weight_result.data_points else None
        )
        resting_heart_rate = (
            hr_result.data_points[0].data if hr_result.data_points else None
        )
        body_fat = (
            body_fat_result.data_points[0].data if body_fat_result.data_points else None
        )

        return GoogleHealthBodyData(
            weight=weight,
            resting_heart_rate=resting_heart_rate,
            body_fat=body_fat,
        )
