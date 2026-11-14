"""Helpers to make instant statistics about your history."""

from collections.abc import Mapping
from dataclasses import dataclass
import datetime as dt
import logging
import math
from typing import Any

from homeassistant.components.sensor import CONF_STATE_CLASS, SensorStateClass
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DURATION,
    CONF_END,
    CONF_PERIOD,
    CONF_START,
    CONF_TYPE_RATIO,
    Period,
)

_LOGGER = logging.getLogger(__name__)


DURATION_START = "start"
DURATION_END = "end"

PERIOD_TEMPLATES: dict[Period, tuple[str | None, str]] = {
    Period.TODAY: ("{{ today_at() }}", "{{ now() }}"),
    Period.YESTERDAY: ("{{ today_at() - timedelta(days=1) }}", "{{ today_at() }}"),
    Period.ROLLING_WINDOW: (None, "{{ now() }}"),
}


@dataclass(frozen=True, slots=True)
class PeriodConfig:
    """Period and state class resolved from config entry options."""

    start: str | None
    end: str | None
    duration: dt.timedelta | None
    state_class: SensorStateClass | None


def resolve_period_config(options: Mapping[str, Any], sensor_type: str) -> PeriodConfig:
    """Resolve the period and state class of a period preset."""
    duration: dt.timedelta | None = None
    if duration_dict := options.get(CONF_DURATION):
        duration = dt.timedelta(**duration_dict)

    if (period := Period(options[CONF_PERIOD])) is Period.CUSTOM:
        return PeriodConfig(
            options.get(CONF_START),
            options.get(CONF_END),
            duration,
            options.get(CONF_STATE_CLASS),
        )

    start, end = PERIOD_TEMPLATES[period]
    # Yesterday's value jumps at midnight, which total_increasing would count as growth
    state_class = (
        SensorStateClass.TOTAL_INCREASING
        if period == Period.TODAY and sensor_type != CONF_TYPE_RATIO
        else SensorStateClass.MEASUREMENT
    )
    return PeriodConfig(
        start,
        end,
        duration if period == Period.ROLLING_WINDOW else None,
        state_class,
    )


@callback
def async_calculate_period(
    duration: dt.timedelta | None,
    start_template: Template | None,
    end_template: Template | None,
    log_errors: bool = True,
) -> tuple[dt.datetime, dt.datetime]:
    """Parse the templates and return the period."""
    bounds: dict[str, dt.datetime | None] = {
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
            rendered = template.async_render(
                log_fn=None if log_errors else lambda *args, **kwargs: None
            )
        except (TemplateError, TypeError) as ex:
            if (
                log_errors
                and ex.args
                and not ex.args[0].startswith("UndefinedError: 'None' has no attribute")
            ):
                _LOGGER.error("Error parsing template for field %s", bound, exc_info=ex)
            raise type(ex)(f"Error parsing template for field {bound}: {ex}") from ex
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


def pretty_ratio(value: float, period: tuple[dt.datetime, dt.datetime]) -> float:
    """Format the ratio of value / period duration."""
    # Subtracting datetimes of the same time zone ignores daylight saving changes
    duration = dt_util.as_utc(period[1]) - dt_util.as_utc(period[0])
    # Bounds in a skipped hour can be distinct datetimes at the same instant
    if not duration:
        return 0.0

    ratio = 100 * value / duration.total_seconds()
    return round(ratio, 1)


def floored_timestamp(incoming_dt: dt.datetime) -> float:
    """Calculate the floored value of a timestamp."""
    return math.floor(dt_util.as_timestamp(incoming_dt))
