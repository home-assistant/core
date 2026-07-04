"""Services for the Sun integration."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final

from astral import Observer
import astral.sun
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import DATA_COMPONENT, DOMAIN, STATE_ATTR_AZIMUTH, STATE_ATTR_ELEVATION

if TYPE_CHECKING:
    from .entity import Sun

SERVICE_GET_POSITIONS: Final = "get_positions"

ATTR_START_DATE_TIME: Final = "start_date_time"
ATTR_END_DATE_TIME: Final = "end_date_time"
ATTR_DURATION: Final = "duration"
ATTR_INTERVAL: Final = "interval"
ATTR_POSITIONS: Final = "positions"
ATTR_DATETIME: Final = "datetime"

DEFAULT_DURATION: Final = timedelta(days=1)
DEFAULT_INTERVAL: Final = timedelta(minutes=5)
MIN_INTERVAL: Final = timedelta(seconds=1)

# Highest number of samples a single call may return (14 days at the default
# 5-minute interval), bounding the computation a call can request.
MAX_POSITIONS: Final = 4032

SERVICE_GET_POSITIONS_SCHEMA: Final = vol.All(
    cv.has_at_most_one_key(ATTR_END_DATE_TIME, ATTR_DURATION),
    cv.make_entity_service_schema(
        {
            vol.Optional(ATTR_START_DATE_TIME): cv.datetime,
            vol.Optional(ATTR_END_DATE_TIME): cv.datetime,
            vol.Optional(ATTR_DURATION): vol.All(cv.time_period, cv.positive_timedelta),
            # positive_timedelta allows zero; the explicit floor also keeps a
            # single call from requesting sub-second sampling.
            vol.Optional(ATTR_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
                cv.time_period, vol.Range(min=MIN_INTERVAL)
            ),
        }
    ),
)


def _compute_positions(
    observer: Observer, start: datetime, end: datetime, interval: timedelta
) -> list[JsonValueType]:
    """Sample the solar trajectory over the requested time range."""
    positions: list[JsonValueType] = []
    sample = start
    while sample <= end:
        positions.append(
            {
                ATTR_DATETIME: sample.isoformat(),
                STATE_ATTR_AZIMUTH: round(astral.sun.azimuth(observer, sample), 2),
                STATE_ATTR_ELEVATION: round(astral.sun.elevation(observer, sample), 2),
            }
        )
        sample += interval
    return positions


async def _async_get_positions(sun: Sun, call: ServiceCall) -> ServiceResponse:
    """Return the solar azimuth and elevation over the requested time range."""
    start = dt_util.as_utc(call.data.get(ATTR_START_DATE_TIME, dt_util.now()))
    if (duration := call.data.get(ATTR_DURATION)) is not None:
        end = start + duration
    elif (end_date_time := call.data.get(ATTR_END_DATE_TIME)) is not None:
        end = dt_util.as_utc(end_date_time)
    else:
        end = start + DEFAULT_DURATION
    if end <= start:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="end_before_start",
        )
    interval: timedelta = call.data[ATTR_INTERVAL]
    count = int((end - start) / interval) + 1
    if count > MAX_POSITIONS:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="too_many_positions",
            translation_placeholders={
                "requested": str(count),
                "limit": str(MAX_POSITIONS),
            },
        )
    # The astral calls are pure CPU-bound math; a wide range at a small
    # interval is thousands of them, so compute off the event loop.
    positions = await sun.hass.async_add_executor_job(
        _compute_positions, sun.observer, start, end, interval
    )
    return {ATTR_POSITIONS: positions}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Sun services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        SERVICE_GET_POSITIONS,
        SERVICE_GET_POSITIONS_SCHEMA,
        _async_get_positions,
        supports_response=SupportsResponse.ONLY,
    )
