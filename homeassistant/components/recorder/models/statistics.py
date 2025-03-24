"""Models for statistics in the Recorder."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, TypedDict


class StatisticResult(TypedDict):
    """Statistic result data class.

    Allows multiple datapoints for the same statistic_id.
    """

    meta: StatisticMetaData
    stat: StatisticData


class StatisticDataTimestampBase(TypedDict):
    """Mandatory fields for statistic data class with a timestamp."""

    start_ts: float


class StatisticDataBase(TypedDict):
    """Mandatory fields for statistic data class."""

    start: datetime


class StatisticMixIn(TypedDict, total=False):
    """Mandatory fields for statistic data class."""

    state: float
    sum: float
    min: float
    max: float
    mean: float


class StatisticData(StatisticDataBase, StatisticMixIn, total=False):
    """Statistic data class."""

    last_reset: datetime | None


class StatisticDataTimestamp(StatisticDataTimestampBase, StatisticMixIn, total=False):
    """Statistic data class with a timestamp."""

    last_reset_ts: float | None


class StatisticMetaData(TypedDict):
    """Statistic meta data class."""

    has_mean: bool
    has_sum: bool
    name: str | None
    source: str
    statistic_id: str
    unit_of_measurement: str | None


class CalendarStatisticPeriod(TypedDict, total=False):
    """Statistic period definition."""

    period: Literal["hour", "day", "week", "month", "year"]
    offset: int


class FixedStatisticPeriod(TypedDict, total=False):
    """Statistic period definition."""

    end_time: datetime
    start_time: datetime


class RollingWindowStatisticPeriod(TypedDict, total=False):
    """Statistic period definition."""

    duration: timedelta
    offset: timedelta


class StatisticPeriod(TypedDict, total=False):
    """Statistic period definition."""

    calendar: CalendarStatisticPeriod
    fixed_period: FixedStatisticPeriod
    rolling_window: RollingWindowStatisticPeriod
