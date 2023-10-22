"""Withings coordinator."""
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import TypeVar

from aiowithings import (
    Goals,
    MeasurementType,
    NotificationCategory,
    SleepSummary,
    SleepSummaryDataFields,
    WithingsAuthenticationFailedError,
    WithingsClient,
    WithingsUnauthorizedError,
    aggregate_measurements,
)
from aiowithings.helpers import aggregate_sleep_summary

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import LOGGER

_T = TypeVar("_T")

UPDATE_INTERVAL = timedelta(minutes=10)


class WithingsDataUpdateCoordinator(DataUpdateCoordinator[_T]):
    """Base coordinator."""

    config_entry: ConfigEntry
    _default_update_interval: timedelta | None = UPDATE_INTERVAL
    _last_valid_update: datetime | None = None
    webhooks_connected: bool = False

    def __init__(self, hass: HomeAssistant, client: WithingsClient) -> None:
        """Initialize the Withings data coordinator."""
        super().__init__(
            hass, LOGGER, name="Withings", update_interval=self._default_update_interval
        )
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
        LOGGER.debug("Withings webhook triggered for %s", notification_category)
        await self.async_request_refresh()

    async def _async_update_data(self) -> _T:
        try:
            return await self._internal_update_data()
        except (WithingsUnauthorizedError, WithingsAuthenticationFailedError) as exc:
            raise ConfigEntryAuthFailed from exc

    @abstractmethod
    async def _internal_update_data(self) -> _T:
        """Update coordinator data."""


class WithingsMeasurementDataUpdateCoordinator(
    WithingsDataUpdateCoordinator[dict[MeasurementType, float]]
):
    """Withings measurement coordinator."""

    def __init__(self, hass: HomeAssistant, client: WithingsClient) -> None:
        """Initialize the Withings data coordinator."""
        super().__init__(hass, client)
        self.notification_categories = {
            NotificationCategory.WEIGHT,
            NotificationCategory.ACTIVITY,
            NotificationCategory.PRESSURE,
        }
        self._previous_data: dict[MeasurementType, float] = {}

    async def _internal_update_data(self) -> dict[MeasurementType, float]:
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
        return aggregate_sleep_summary(response)


class WithingsBedPresenceDataUpdateCoordinator(WithingsDataUpdateCoordinator[None]):
    """Withings bed presence coordinator."""

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

    _default_update_interval = timedelta(hours=1)

    def webhook_subscription_listener(self, connected: bool) -> None:
        """Call when webhook status changed."""
        # Webhooks aren't available for this datapoint, so we keep polling

    async def _internal_update_data(self) -> Goals:
        """Retrieve goals data."""
        return await self._client.get_goals()
