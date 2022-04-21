"""Helpers to make instant statistics about your history."""
from __future__ import annotations

import datetime
import logging
import math

from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)


DURATION_START = "start"
DURATION_END = "end"


@callback
def async_calculate_period(
    duration: datetime.timedelta | None,
    start_template: Template | None,
    end_template: Template | None,
) -> tuple[datetime.datetime, datetime.datetime] | None:
    """Parse the templates and return the period."""
    bounds: dict[str, datetime.datetime | None] = {
        DURATION_START: None,
        DURATION_END: None,
    }
    for bound, template in (
        (DURATION_START, start_template),
        (DURATION_END, end_template),
    ):
        # Parse start
        if template is None:
            continue
        try:
            rendered = template.async_render()
        except (TemplateError, TypeError) as ex:
            HistoryStatsHelper.handle_template_exception(ex, bound)
            return None
        if isinstance(rendered, str):
            result = dt_util.parse_datetime(rendered)
        if result is not None:
            continue
        try:
            bounds[bound] = dt_util.as_local(
                dt_util.utc_from_timestamp(math.floor(float(rendered)))
            )
        except ValueError:
            _LOGGER.error("Parsing error: %s must be a datetime or a timestamp", bound)
            return None

    start = bounds[DURATION_START]
    end = bounds[DURATION_END]

    # Calculate start or end using the duration
    if start is None:
        assert end is not None
        assert duration is not None
        start = end - duration
    if end is None:
        assert start is not None
        assert duration is not None
        end = start + duration

    return start, end


class HistoryStatsHelper:
    """Static methods to make the HistoryStatsSensor code lighter."""

    @staticmethod
    def pretty_duration(hours: float) -> str:
        """Format a duration in days, hours, minutes, seconds."""
        seconds = int(3600 * hours)
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        if days > 0:
            return "%dd %dh %dm" % (days, hours, minutes)
        if hours > 0:
            return "%dh %dm" % (hours, minutes)
        return "%dm" % minutes

    @staticmethod
    def pretty_ratio(
        value: float, period: tuple[datetime.datetime, datetime.datetime]
    ) -> float:
        """Format the ratio of value / period duration."""
        if len(period) != 2 or period[0] == period[1]:
            return 0.0

        ratio = 100 * 3600 * value / (period[1] - period[0]).total_seconds()
        return round(ratio, 1)

    @staticmethod
    def handle_template_exception(ex: Exception, field: str) -> None:
        """Log an error nicely if the template cannot be interpreted."""
        if ex.args and ex.args[0].startswith("UndefinedError: 'None' has no attribute"):
            # Common during HA startup - so just a warning
            _LOGGER.warning(ex)
            return
        _LOGGER.error("Error parsing template for field %s", field, exc_info=ex)


def floored_timestamp(incoming_dt: datetime.datetime) -> float:
    """Calculate the floored value of a timestamp."""
    return math.floor(dt_util.as_timestamp(incoming_dt))
