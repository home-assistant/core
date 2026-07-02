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
    DailyRollupDataPoint,
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


@dataclass
class GoogleHealthActivityData:
    """Class to hold activity data."""

    steps: DailyRollupDataPoint[StepsRollupValue] | None = None
    distance: DailyRollupDataPoint[DistanceRollupValue] | None = None


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
            translation_placeholders={"error": str(err)},
        ) from err
    except GoogleHealthApiError as err:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
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
        """Fetch steps and distance rollup for today."""
        with handle_api_errors():
            steps = await self.api.steps.today(self.hass.config.time_zone)
            distance = await self.api.distance.today(self.hass.config.time_zone)
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
        with handle_api_errors():
            weight_result = await self.api.weight.list(page_size=100)
            hr_result = await self.api.daily_resting_heart_rate.list(page_size=100)

        weight = (
            weight_result.data_points[-1].data if weight_result.data_points else None
        )
        resting_heart_rate = (
            hr_result.data_points[-1].data if hr_result.data_points else None
        )

        return GoogleHealthBodyData(
            weight=weight, resting_heart_rate=resting_heart_rate
        )
