"""Withings coordinator."""
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from withings_api.common import (
    AuthFailedException,
    GetSleepSummaryField,
    MeasureGroupAttribs,
    MeasureType,
    MeasureTypes,
    NotifyAppli,
    UnauthorizedException,
    query_measure_groups,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import ConfigEntryWithingsApi
from .const import LOGGER, Measurement

WITHINGS_MEASURE_TYPE_MAP: dict[
    NotifyAppli | GetSleepSummaryField | MeasureType, Measurement
] = {
    MeasureType.WEIGHT: Measurement.WEIGHT_KG,
    MeasureType.FAT_MASS_WEIGHT: Measurement.FAT_MASS_KG,
    MeasureType.FAT_FREE_MASS: Measurement.FAT_FREE_MASS_KG,
    MeasureType.MUSCLE_MASS: Measurement.MUSCLE_MASS_KG,
    MeasureType.BONE_MASS: Measurement.BONE_MASS_KG,
    MeasureType.HEIGHT: Measurement.HEIGHT_M,
    MeasureType.TEMPERATURE: Measurement.TEMP_C,
    MeasureType.BODY_TEMPERATURE: Measurement.BODY_TEMP_C,
    MeasureType.SKIN_TEMPERATURE: Measurement.SKIN_TEMP_C,
    MeasureType.FAT_RATIO: Measurement.FAT_RATIO_PCT,
    MeasureType.DIASTOLIC_BLOOD_PRESSURE: Measurement.DIASTOLIC_MMHG,
    MeasureType.SYSTOLIC_BLOOD_PRESSURE: Measurement.SYSTOLIC_MMGH,
    MeasureType.HEART_RATE: Measurement.HEART_PULSE_BPM,
    MeasureType.SP02: Measurement.SPO2_PCT,
    MeasureType.HYDRATION: Measurement.HYDRATION,
    MeasureType.PULSE_WAVE_VELOCITY: Measurement.PWV,
    GetSleepSummaryField.BREATHING_DISTURBANCES_INTENSITY: (
        Measurement.SLEEP_BREATHING_DISTURBANCES_INTENSITY
    ),
    GetSleepSummaryField.DEEP_SLEEP_DURATION: Measurement.SLEEP_DEEP_DURATION_SECONDS,
    GetSleepSummaryField.DURATION_TO_SLEEP: Measurement.SLEEP_TOSLEEP_DURATION_SECONDS,
    GetSleepSummaryField.DURATION_TO_WAKEUP: (
        Measurement.SLEEP_TOWAKEUP_DURATION_SECONDS
    ),
    GetSleepSummaryField.HR_AVERAGE: Measurement.SLEEP_HEART_RATE_AVERAGE,
    GetSleepSummaryField.HR_MAX: Measurement.SLEEP_HEART_RATE_MAX,
    GetSleepSummaryField.HR_MIN: Measurement.SLEEP_HEART_RATE_MIN,
    GetSleepSummaryField.LIGHT_SLEEP_DURATION: Measurement.SLEEP_LIGHT_DURATION_SECONDS,
    GetSleepSummaryField.REM_SLEEP_DURATION: Measurement.SLEEP_REM_DURATION_SECONDS,
    GetSleepSummaryField.RR_AVERAGE: Measurement.SLEEP_RESPIRATORY_RATE_AVERAGE,
    GetSleepSummaryField.RR_MAX: Measurement.SLEEP_RESPIRATORY_RATE_MAX,
    GetSleepSummaryField.RR_MIN: Measurement.SLEEP_RESPIRATORY_RATE_MIN,
    GetSleepSummaryField.SLEEP_SCORE: Measurement.SLEEP_SCORE,
    GetSleepSummaryField.SNORING: Measurement.SLEEP_SNORING,
    GetSleepSummaryField.SNORING_EPISODE_COUNT: Measurement.SLEEP_SNORING_EPISODE_COUNT,
    GetSleepSummaryField.WAKEUP_COUNT: Measurement.SLEEP_WAKEUP_COUNT,
    GetSleepSummaryField.WAKEUP_DURATION: Measurement.SLEEP_WAKEUP_DURATION_SECONDS,
    NotifyAppli.BED_IN: Measurement.IN_BED,
}

UPDATE_INTERVAL = timedelta(minutes=10)


class WithingsDataUpdateCoordinator(DataUpdateCoordinator[dict[Measurement, Any]]):
    """Base coordinator."""

    in_bed: bool | None = None
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, client: ConfigEntryWithingsApi) -> None:
        """Initialize the Withings data coordinator."""
        super().__init__(hass, LOGGER, name="Withings", update_interval=UPDATE_INTERVAL)
        self._client = client

    def webhook_subscription_listener(self, connected: bool) -> None:
        """Call when webhook status changed."""
        if connected:
            self.update_interval = None
        else:
            self.update_interval = UPDATE_INTERVAL

    async def _async_update_data(self) -> dict[Measurement, Any]:
        try:
            measurements = await self._get_measurements()
            sleep_summary = await self._get_sleep_summary()
        except (UnauthorizedException, AuthFailedException) as exc:
            raise ConfigEntryAuthFailed from exc
        return {
            **measurements,
            **sleep_summary,
        }

    async def _get_measurements(self) -> dict[Measurement, Any]:
        LOGGER.debug("Updating withings measures")
        now = dt_util.utcnow()
        startdate = now - timedelta(days=7)

        response = await self._client.async_measure_get_meas(
            None, None, startdate, now, None, startdate
        )

        # Sort from oldest to newest.
        groups = sorted(
            query_measure_groups(
                response, MeasureTypes.ANY, MeasureGroupAttribs.UNAMBIGUOUS
            ),
            key=lambda group: group.created.datetime,
            reverse=False,
        )

        return {
            WITHINGS_MEASURE_TYPE_MAP[measure.type]: round(
                float(measure.value * pow(10, measure.unit)), 2
            )
            for group in groups
            for measure in group.measures
            if measure.type in WITHINGS_MEASURE_TYPE_MAP
        }

    async def _get_sleep_summary(self) -> dict[Measurement, Any]:
        now = dt_util.now()
        yesterday = now - timedelta(days=1)
        yesterday_noon = dt_util.start_of_local_day(yesterday) + timedelta(hours=12)
        yesterday_noon_utc = dt_util.as_utc(yesterday_noon)

        response = await self._client.async_sleep_get_summary(
            lastupdate=yesterday_noon_utc,
            data_fields=[
                GetSleepSummaryField.BREATHING_DISTURBANCES_INTENSITY,
                GetSleepSummaryField.DEEP_SLEEP_DURATION,
                GetSleepSummaryField.DURATION_TO_SLEEP,
                GetSleepSummaryField.DURATION_TO_WAKEUP,
                GetSleepSummaryField.HR_AVERAGE,
                GetSleepSummaryField.HR_MAX,
                GetSleepSummaryField.HR_MIN,
                GetSleepSummaryField.LIGHT_SLEEP_DURATION,
                GetSleepSummaryField.REM_SLEEP_DURATION,
                GetSleepSummaryField.RR_AVERAGE,
                GetSleepSummaryField.RR_MAX,
                GetSleepSummaryField.RR_MIN,
                GetSleepSummaryField.SLEEP_SCORE,
                GetSleepSummaryField.SNORING,
                GetSleepSummaryField.SNORING_EPISODE_COUNT,
                GetSleepSummaryField.WAKEUP_COUNT,
                GetSleepSummaryField.WAKEUP_DURATION,
            ],
        )

        # Set the default to empty lists.
        raw_values: dict[GetSleepSummaryField, list[int]] = {
            field: [] for field in GetSleepSummaryField
        }

        # Collect the raw data.
        for serie in response.series:
            data = serie.data

            for field in GetSleepSummaryField:
                raw_values[field].append(dict(data)[field.value])

        values: dict[GetSleepSummaryField, float] = {}

        def average(data: list[int]) -> float:
            return sum(data) / len(data)

        def set_value(field: GetSleepSummaryField, func: Callable) -> None:
            non_nones = [
                value for value in raw_values.get(field, []) if value is not None
            ]
            values[field] = func(non_nones) if non_nones else None

        set_value(GetSleepSummaryField.BREATHING_DISTURBANCES_INTENSITY, average)
        set_value(GetSleepSummaryField.DEEP_SLEEP_DURATION, sum)
        set_value(GetSleepSummaryField.DURATION_TO_SLEEP, average)
        set_value(GetSleepSummaryField.DURATION_TO_WAKEUP, average)
        set_value(GetSleepSummaryField.HR_AVERAGE, average)
        set_value(GetSleepSummaryField.HR_MAX, average)
        set_value(GetSleepSummaryField.HR_MIN, average)
        set_value(GetSleepSummaryField.LIGHT_SLEEP_DURATION, sum)
        set_value(GetSleepSummaryField.REM_SLEEP_DURATION, sum)
        set_value(GetSleepSummaryField.RR_AVERAGE, average)
        set_value(GetSleepSummaryField.RR_MAX, average)
        set_value(GetSleepSummaryField.RR_MIN, average)
        set_value(GetSleepSummaryField.SLEEP_SCORE, max)
        set_value(GetSleepSummaryField.SNORING, average)
        set_value(GetSleepSummaryField.SNORING_EPISODE_COUNT, sum)
        set_value(GetSleepSummaryField.WAKEUP_COUNT, sum)
        set_value(GetSleepSummaryField.WAKEUP_DURATION, average)

        return {
            WITHINGS_MEASURE_TYPE_MAP[field]: round(value, 4)
            if value is not None
            else None
            for field, value in values.items()
        }

    async def async_webhook_data_updated(
        self, notification_category: NotifyAppli
    ) -> None:
        """Update data when webhook is called."""
        LOGGER.debug("Withings webhook triggered")
        if notification_category in {
            NotifyAppli.WEIGHT,
            NotifyAppli.CIRCULATORY,
            NotifyAppli.SLEEP,
        }:
            await self.async_request_refresh()

        elif notification_category in {NotifyAppli.BED_IN, NotifyAppli.BED_OUT}:
            self.in_bed = notification_category == NotifyAppli.BED_IN
            self.async_update_listeners()
