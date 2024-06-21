"""Withings coordinator."""

from __future__ import annotations

from abc import abstractmethod
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from aiowithings import (
    Activity,
    Goals,
    MeasurementPosition,
    MeasurementType,
    NotificationCategory,
    SleepSummary,
    SleepSummaryDataFields,
    WithingsAuthenticationFailedError,
    WithingsClient,
    WithingsUnauthorizedError,
    Workout,
    aggregate_measurements,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import LOGGER

if TYPE_CHECKING:
    from . import WithingsConfigEntry

UPDATE_INTERVAL = timedelta(minutes=10)


class WithingsDataUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base coordinator."""

    config_entry: WithingsConfigEntry
    _default_update_interval: timedelta | None = UPDATE_INTERVAL
    _last_valid_update: datetime | None = None
    webhooks_connected: bool = False
    coordinator_name: str = ""

    def __init__(self, hass: HomeAssistant, client: WithingsClient) -> None:
        """Initialize the Withings data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="",
            update_interval=self._default_update_interval,
        )
        self.name = f"Withings {self.config_entry.unique_id} {self.coordinator_name}"
        self._client = client
        self.notification_categories: set[NotificationCategory] = set()

    def webhook_subscription_listener(self, connected: bool) -> None:
        """Call when webhook status changed."""
        self.webhooks_connected = connected
        if connected:
            self.update_interval = None
        else:
            self.update_interval = self._default_update_interval

    async def async_webhook_data_updated(
        self, notification_category: NotificationCategory
    ) -> None:
        """Update data when webhook is called."""
        LOGGER.debug(
            "Withings webhook triggered for category %s for user %s",
            notification_category,
            self.config_entry.unique_id,
        )
        await self.async_request_refresh()

    async def _async_update_data(self) -> _DataT:
        try:
            return await self._internal_update_data()
        except (WithingsUnauthorizedError, WithingsAuthenticationFailedError) as exc:
            raise ConfigEntryAuthFailed from exc

    @abstractmethod
    async def _internal_update_data(self) -> _DataT:
        """Update coordinator data."""


class WithingsMeasurementDataUpdateCoordinator(
    WithingsDataUpdateCoordinator[
        dict[tuple[MeasurementType, MeasurementPosition | None], float]
    ]
):
    """Withings measurement coordinator."""

    coordinator_name: str = "measurements"

    def __init__(self, hass: HomeAssistant, client: WithingsClient) -> None:
        """Initialize the Withings data coordinator."""
        super().__init__(hass, client)
        self.notification_categories = {
            NotificationCategory.WEIGHT,
            NotificationCategory.PRESSURE,
        }
        self._previous_data: dict[
            tuple[MeasurementType, MeasurementPosition | None], float
        ] = {}

    async def _internal_update_data(
        self,
    ) -> dict[tuple[MeasurementType, MeasurementPosition | None], float]:
        """Retrieve measurement data."""
        if self._last_valid_update is None:
            now = dt_util.utcnow()
            startdate = now - timedelta(days=14)
            measurements = await self._client.get_measurement_in_period(startdate, now)
        else:
            measurements = await self._client.get_measurement_since(
                self._last_valid_update
            )

        if measurements:
            self._last_valid_update = measurements[0].taken_at
            aggregated_measurements = aggregate_measurements(measurements)
            self._previous_data.update(aggregated_measurements)
        return self._previous_data


class WithingsSleepDataUpdateCoordinator(
    WithingsDataUpdateCoordinator[SleepSummary | None]
):
    """Withings sleep coordinator."""

    coordinator_name: str = "sleep"

    def __init__(self, hass: HomeAssistant, client: WithingsClient) -> None:
        """Initialize the Withings data coordinator."""
        super().__init__(hass, client)
        self.notification_categories = {
            NotificationCategory.SLEEP,
        }

    async def _internal_update_data(self) -> SleepSummary | None:
        """Retrieve sleep data."""
        now = dt_util.now()
        yesterday = now - timedelta(days=1)
        yesterday_noon = dt_util.start_of_local_day(yesterday) + timedelta(hours=12)
        yesterday_noon_utc = dt_util.as_utc(yesterday_noon)

        response = await self._client.get_sleep_summary_since(
            sleep_summary_since=yesterday_noon_utc,
            sleep_summary_data_fields=[
                SleepSummaryDataFields.BREATHING_DISTURBANCES_INTENSITY,
                SleepSummaryDataFields.DEEP_SLEEP_DURATION,
                SleepSummaryDataFields.SLEEP_LATENCY,
                SleepSummaryDataFields.WAKE_UP_LATENCY,
                SleepSummaryDataFields.AVERAGE_HEART_RATE,
                SleepSummaryDataFields.MIN_HEART_RATE,
                SleepSummaryDataFields.MAX_HEART_RATE,
                SleepSummaryDataFields.LIGHT_SLEEP_DURATION,
                SleepSummaryDataFields.REM_SLEEP_DURATION,
                SleepSummaryDataFields.AVERAGE_RESPIRATION_RATE,
                SleepSummaryDataFields.MIN_RESPIRATION_RATE,
                SleepSummaryDataFields.MAX_RESPIRATION_RATE,
                SleepSummaryDataFields.SLEEP_SCORE,
                SleepSummaryDataFields.SNORING,
                SleepSummaryDataFields.SNORING_COUNT,
                SleepSummaryDataFields.WAKE_UP_COUNT,
                SleepSummaryDataFields.TOTAL_TIME_AWAKE,
            ],
        )
        if not response:
            return None

        return sorted(
            response, key=lambda sleep_summary: sleep_summary.end_date, reverse=True
        )[0]


class WithingsBedPresenceDataUpdateCoordinator(WithingsDataUpdateCoordinator[None]):
    """Withings bed presence coordinator."""

    coordinator_name: str = "bed presence"
    in_bed: bool | None = None
    _default_update_interval = None

    def __init__(self, hass: HomeAssistant, client: WithingsClient) -> None:
        """Initialize the Withings data coordinator."""
        super().__init__(hass, client)
        self.notification_categories = {
            NotificationCategory.IN_BED,
            NotificationCategory.OUT_BED,
        }

    async def async_webhook_data_updated(
        self, notification_category: NotificationCategory
    ) -> None:
        """Only set new in bed value instead of refresh."""
        self.in_bed = notification_category == NotificationCategory.IN_BED
        self.async_update_listeners()

    async def _internal_update_data(self) -> None:
        """Update coordinator data."""


class WithingsGoalsDataUpdateCoordinator(WithingsDataUpdateCoordinator[Goals]):
    """Withings goals coordinator."""

    coordinator_name: str = "goals"
    _default_update_interval = timedelta(hours=1)

    def webhook_subscription_listener(self, connected: bool) -> None:
        """Call when webhook status changed."""
        # Webhooks aren't available for this datapoint, so we keep polling

    async def _internal_update_data(self) -> Goals:
        """Retrieve goals data."""
        return await self._client.get_goals()


class WithingsActivityDataUpdateCoordinator(
    WithingsDataUpdateCoordinator[Activity | None]
):
    """Withings activity coordinator."""

    coordinator_name: str = "activity"
    _previous_data: Activity | None = None

    def __init__(self, hass: HomeAssistant, client: WithingsClient) -> None:
        """Initialize the Withings data coordinator."""
        super().__init__(hass, client)
        self.notification_categories = {
            NotificationCategory.ACTIVITY,
        }

    async def _internal_update_data(self) -> Activity | None:
        """Retrieve latest activity."""
        if self._last_valid_update is None:
            now = dt_util.utcnow()
            startdate = now - timedelta(days=14)
            activities = await self._client.get_activities_in_period(
                startdate.date(), now.date()
            )
        else:
            activities = await self._client.get_activities_since(
                self._last_valid_update
            )

        today = date.today()
        for activity in activities:
            if activity.date == today:
                self._previous_data = activity
                self._last_valid_update = activity.modified
                return activity
        if self._previous_data and self._previous_data.date == today:
            return self._previous_data
        return None


class WithingsWorkoutDataUpdateCoordinator(
    WithingsDataUpdateCoordinator[Workout | None]
):
    """Withings workout coordinator."""

    coordinator_name: str = "workout"
    _previous_data: Workout | None = None

    def __init__(self, hass: HomeAssistant, client: WithingsClient) -> None:
        """Initialize the Withings data coordinator."""
        super().__init__(hass, client)
        self.notification_categories = {
            NotificationCategory.ACTIVITY,
        }

    async def _internal_update_data(self) -> Workout | None:
        """Retrieve latest workout."""
        if self._last_valid_update is None:
            now = dt_util.utcnow()
            startdate = now - timedelta(days=14)
            workouts = await self._client.get_workouts_in_period(
                startdate.date(), now.date()
            )
        else:
            workouts = await self._client.get_workouts_since(self._last_valid_update)
        if not workouts:
            return self._previous_data
        latest_workout = max(workouts, key=lambda workout: workout.end_date)
        if (
            self._previous_data is None
            or self._previous_data.end_date >= latest_workout.end_date
        ):
            self._previous_data = latest_workout
            self._last_valid_update = latest_workout.end_date
        return self._previous_data
