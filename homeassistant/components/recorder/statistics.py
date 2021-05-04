"""Statistics helper."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import TYPE_CHECKING

import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .models import Statistics
from .util import session_scope, try_database_job

if TYPE_CHECKING:
    from . import Recorder

_LOGGER = logging.getLogger(__name__)


def get_start_time(period: str) -> datetime.datetime:
    """Return start time give a period."""
    if period == "daily":
        # Get start and end times at local midnigt. This will result in a period of 23 hours
        # at start of DST and a period of 25 hours at end of DST
        yesterday = date.today() - timedelta(days=1)
        start = datetime.combine(yesterday, datetime.min.time()).astimezone(
            dt_util.NATIVE_UTC
        )
    else:
        last_hour = dt_util.utcnow() - timedelta(hours=1)
        start = last_hour.replace(minute=0, second=0, microsecond=0)
    return start


def compile_statistics(
    instance: Recorder, period: str, start: datetime.datetime
) -> bool:
    """Compile statistics."""
    return try_database_job(
        instance, "statistics", _compile_statistics, instance, period, start
    )


def _compile_statistics(instance: Recorder, period: str, start: datetime.datetime):
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
            for entity_id, stat in stats.items():
                session.add(Statistics.from_stats(entity_id, period, start, end, stat))

    return True
