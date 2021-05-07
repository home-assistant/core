"""Statistics helper."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import TYPE_CHECKING

import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .models import Statistics
from .util import retriable_database_job, session_scope

STATISTIC_COLUMN_MAP = {
    "min_max": {
        "max": "value_1",
        "min": "value_2",
        "mean": "value_3",
    }
}

if TYPE_CHECKING:
    from . import Recorder

_LOGGER = logging.getLogger(__name__)


def get_start_time(period: str) -> datetime.datetime:
    """Return start time give a period."""
    if period == "daily":
        # Get start and end times at local midnight. This will result in a period of
        # 23 hours at start of DST and a period of 25 hours at end of DST
        start = dt_util.start_of_local_day(date.today() - timedelta(days=1))
    else:
        last_hour = dt_util.utcnow() - timedelta(hours=1)
        start = last_hour.replace(minute=0, second=0, microsecond=0)
    return start


@retriable_database_job("statistics")
def compile_statistics(
    instance: Recorder, period: str, start: datetime.datetime
) -> bool:
    """Compile statistics."""
    start = dt_util.as_utc(start)
    if period == "daily":
        end = start + timedelta(days=1)
    else:
        end = start + timedelta(hours=1)
    _LOGGER.debug(
        "Compiling statistics for %s-%s",
        start,
        end,
    )
    platform_stats = []
    for domain, platform in instance.hass.data[DOMAIN].items():
        if not hasattr(platform, "compile_statistics"):
            continue
        platform_stats.append(platform.compile_statistics(instance.hass, start, end))
        _LOGGER.debug(
            "Statistics for %s during %s-%s: %s", domain, start, end, platform_stats[-1]
        )

    with session_scope(session=instance.get_session()) as session:  # type: ignore
        for stats in platform_stats:
            for entity_id, data in stats.items():
                statistic_type = data.pop("statistic_type")
                column_map = STATISTIC_COLUMN_MAP[statistic_type]
                stat = {column: data.get(key) for (key, column) in column_map.items()}
                session.add(
                    Statistics.from_stats(
                        entity_id, period, start, statistic_type, stat
                    )
                )

    return True
