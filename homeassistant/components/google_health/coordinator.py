"""Coordinators for Google Health."""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from google_health_api import GoogleHealthApi
from google_health_api.exceptions import (
    GoogleHealthApiError,
    HealthApiForbiddenException,
    HealthAuthException,
)
from google_health_api.model import (
    DailyRestingHeartRate,
    DistanceRollupValue,
    StepsRollupValue,
    Weight,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

POLLING_INTERVAL = timedelta(minutes=15)
BODY_POLLING_INTERVAL = timedelta(hours=1)
DEFAULT_PAGE_SIZE = 1


@dataclass
class GoogleHealthActivityData:
    """Class to hold activity data."""

    steps: StepsRollupValue | None = None
    distance: DistanceRollupValue | None = None


@dataclass
class GoogleHealthBodyData:
    """Class to hold body measurements."""

    weight: Weight | None = None
    resting_heart_rate: DailyRestingHeartRate | None = None


@contextmanager
def handle_api_errors() -> Generator[None]:
    """Context manager to handle Google Health API errors."""
    try:
        yield
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


class GoogleHealthActivityCoordinator(DataUpdateCoordinator[GoogleHealthActivityData]):
    """Coordinator to fetch activity data from Google Health API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_client: GoogleHealthApi,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api_client
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_activity",
            update_interval=POLLING_INTERVAL,
            config_entry=entry,
        )

    @override
    async def _async_update_data(self) -> GoogleHealthActivityData:
        """Fetch steps and distance rollup for today.

        Queries the daily rollup endpoints using Home Assistant's local time zone
        to aggregate step and distance counts over the current civil day. If no
        data points exist for today yet, the API returns None, which the sensors
        default to 0.
        """
        with handle_api_errors():
            steps_rollup = await self.api.steps.today(self.hass.config.time_zone)
            distance_rollup = await self.api.distance.today(self.hass.config.time_zone)

        steps = steps_rollup.data if steps_rollup else None
        distance = distance_rollup.data if distance_rollup else None

        return GoogleHealthActivityData(steps=steps, distance=distance)


class GoogleHealthBodyCoordinator(DataUpdateCoordinator[GoogleHealthBodyData]):
    """Coordinator to fetch body measurements from Google Health API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_client: GoogleHealthApi,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api_client
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_body",
            update_interval=BODY_POLLING_INTERVAL,
            config_entry=entry,
        )

    @override
    async def _async_update_data(self) -> GoogleHealthBodyData:
        """Fetch latest body weight and resting heart rate."""
        # The Google Health API returns data points sorted by interval start time
        # in descending order (newest first). Querying with page_size=1 and grabbing
        # the first element is sufficient to fetch the most recent measurement.
        with handle_api_errors():
            weight_result = await self.api.weight.list(page_size=DEFAULT_PAGE_SIZE)
            hr_result = await self.api.daily_resting_heart_rate.list(
                page_size=DEFAULT_PAGE_SIZE
            )

        weight = (
            weight_result.data_points[0].data if weight_result.data_points else None
        )
        resting_heart_rate = (
            hr_result.data_points[0].data if hr_result.data_points else None
        )

        return GoogleHealthBodyData(
            weight=weight, resting_heart_rate=resting_heart_rate
        )
