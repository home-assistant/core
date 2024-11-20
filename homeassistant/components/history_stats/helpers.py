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
) -> tuple[datetime.datetime, datetime.datetime]:
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
            if ex.args and not ex.args[0].startswith(
                "UndefinedError: 'None' has no attribute"
            ):
                _LOGGER.error("Error parsing template for field %s", bound, exc_info=ex)
            raise
        if isinstance(rendered, str):
            bounds[bound] = dt_util.parse_datetime(rendered)
        if bounds[bound] is not None:
            continue
        try:
            bounds[bound] = dt_util.as_local(
                dt_util.utc_from_timestamp(math.floor(float(rendered)))
            )
        except ValueError as ex:
            raise ValueError(
                f"Parsing error: {bound} must be a datetime or a timestamp: {ex}"
            ) from ex

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


def pretty_ratio(
    value: float, period: tuple[datetime.datetime, datetime.datetime]
) -> float:
    """Format the ratio of value / period duration."""
    if len(period) != 2 or period[0] == period[1]:
        return 0.0

    ratio = 100 * value / (period[1] - period[0]).total_seconds()
    return round(ratio, 1)


def floored_timestamp(incoming_dt: datetime.datetime) -> float:
    """Calculate the floored value of a timestamp."""
    return math.floor(dt_util.as_timestamp(incoming_dt))
