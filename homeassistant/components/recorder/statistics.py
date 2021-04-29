"""Statistics helper."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging
import time
from typing import TYPE_CHECKING

from sqlalchemy.exc import OperationalError

import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .models import Statistics
from .util import session_scope

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
    try:
        with session_scope(session=instance.get_session()) as session:  # type: ignore
            for domain, platform in instance.hass.data[DOMAIN].items():
                if not hasattr(platform, "async_compile_statistics"):
                    continue
                stats = asyncio.run_coroutine_threadsafe(
                    platform.async_compile_statistics(instance.hass, start, end),
                    instance.hass.loop,
                ).result()
                _LOGGER.debug(
                    "Statistics for %s during %s-%s: %s", domain, start, end, stats
                )
                for entity_id, stat in stats.items():
                    session.add(
                        Statistics.from_stats(entity_id, period, start, end, stat)
                    )
    except OperationalError as err:
        # Retry when one of the following MySQL errors occurred:
        # 1205: Lock wait timeout exceeded; try restarting transaction
        # 1206: The total number of locks exceeds the lock table size
        # 1213: Deadlock found when trying to get lock; try restarting transaction
        if instance.engine.driver in ("mysqldb", "pymysql") and err.orig.args[0] in (
            1205,
            1206,
            1213,
        ):
            _LOGGER.info("%s; statistics run completed, retrying", err.orig.args[1])
            time.sleep(instance.db_retry_wait)
            return False

        _LOGGER.warning("Error compiling statistics: %s", err)

    return True
