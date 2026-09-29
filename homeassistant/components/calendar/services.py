"""Services for the calendar integration."""

import dataclasses
import datetime
from typing import TYPE_CHECKING, Any, Final

import probatio

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    CREATE_EVENT_SERVICE,
    DATA_COMPONENT,
    EVENT_DESCRIPTION,
    EVENT_DURATION,
    EVENT_END,
    EVENT_END_DATE,
    EVENT_END_DATETIME,
    EVENT_IN,
    EVENT_IN_DAYS,
    EVENT_IN_WEEKS,
    EVENT_LOCATION,
    EVENT_START,
    EVENT_START_DATE,
    EVENT_START_DATETIME,
    EVENT_SUMMARY,
    EVENT_TIME_FIELDS,
    EVENT_TYPES,
    SERVICE_GET_EVENTS,
    CalendarEntityFeature,
)
from .helper import (
    MIN_NEW_EVENT_DURATION,
    as_local_timezone,
    has_consistent_timezone,
    has_min_duration,
    has_positive_interval,
    list_events_dict_factory,
)

if TYPE_CHECKING:
    from . import CalendarEntity

CREATE_EVENT_SCHEMA = probatio.All(
    cv.has_at_least_one_key(EVENT_START_DATE, EVENT_START_DATETIME, EVENT_IN),
    cv.has_at_most_one_key(EVENT_START_DATE, EVENT_START_DATETIME, EVENT_IN),
    cv.make_entity_service_schema(
        {
            probatio.Required(EVENT_SUMMARY): cv.string,
            probatio.Optional(EVENT_DESCRIPTION, default=""): cv.string,
            probatio.Optional(EVENT_LOCATION): cv.string,
            probatio.Inclusive(
                EVENT_START_DATE, "dates", "Start and end dates must both be specified"
            ): cv.date,
            probatio.Inclusive(
                EVENT_END_DATE, "dates", "Start and end dates must both be specified"
            ): cv.date,
            probatio.Inclusive(
                EVENT_START_DATETIME,
                "datetimes",
                "Start and end datetimes must both be specified",
            ): cv.datetime,
            probatio.Inclusive(
                EVENT_END_DATETIME,
                "datetimes",
                "Start and end datetimes must both be specified",
            ): cv.datetime,
            probatio.Optional(EVENT_IN): probatio.Schema(
                {
                    probatio.Exclusive(EVENT_IN_DAYS, EVENT_TYPES): cv.positive_int,
                    probatio.Exclusive(EVENT_IN_WEEKS, EVENT_TYPES): cv.positive_int,
                }
            ),
        },
    ),
    has_consistent_timezone(EVENT_START_DATETIME, EVENT_END_DATETIME),
    as_local_timezone(EVENT_START_DATETIME, EVENT_END_DATETIME),
    has_min_duration(EVENT_START_DATE, EVENT_END_DATE, MIN_NEW_EVENT_DURATION),
    has_min_duration(EVENT_START_DATETIME, EVENT_END_DATETIME, MIN_NEW_EVENT_DURATION),
)


SERVICE_GET_EVENTS_SCHEMA: Final = probatio.All(
    cv.has_at_least_one_key(EVENT_END_DATETIME, EVENT_DURATION),
    cv.has_at_most_one_key(EVENT_END_DATETIME, EVENT_DURATION),
    cv.make_entity_service_schema(
        {
            probatio.Optional(EVENT_START_DATETIME): cv.datetime,
            probatio.Optional(EVENT_END_DATETIME): cv.datetime,
            probatio.Optional(EVENT_DURATION): probatio.All(
                cv.time_period, cv.positive_timedelta
            ),
        }
    ),
    has_positive_interval(EVENT_START_DATETIME, EVENT_END_DATETIME, EVENT_DURATION),
)


def _validate_timespan(
    values: dict[str, Any],
) -> tuple[datetime.datetime | datetime.date, datetime.datetime | datetime.date]:
    """Parse a create event service call.

    Convert the args for a create event entity call.
    This converts the input service arguments into a
    `start` and `end` date or date time. This exists because
    service calls use `start_date` and `start_date_time`
    whereas the normal entity methods can take either a
    `datetime` or `date` as a single `start` argument.
    It also handles the other service call variations like "in days" as well.
    """

    if event_in := values.get(EVENT_IN):
        days = event_in.get(EVENT_IN_DAYS, 7 * event_in.get(EVENT_IN_WEEKS, 0))
        today = dt_util.now().date()
        return (
            today + datetime.timedelta(days=days),
            today + datetime.timedelta(days=days + 1),
        )

    if EVENT_START_DATE in values and EVENT_END_DATE in values:
        return (values[EVENT_START_DATE], values[EVENT_END_DATE])

    if EVENT_START_DATETIME in values and EVENT_END_DATETIME in values:
        return (values[EVENT_START_DATETIME], values[EVENT_END_DATETIME])

    raise ValueError("Missing required fields to set start or end date/datetime")


async def async_create_event(entity: CalendarEntity, call: ServiceCall) -> None:
    """Add a new event to calendar."""
    # Convert parameters to format used by async_create_event
    (start, end) = _validate_timespan(call.data)
    params = {
        **{k: v for k, v in call.data.items() if k not in EVENT_TIME_FIELDS},
        EVENT_START: start,
        EVENT_END: end,
    }
    await entity.async_create_event(**params)


async def async_get_events_service(
    calendar: CalendarEntity, service_call: ServiceCall
) -> ServiceResponse:
    """List events on a calendar during a time range."""
    start = service_call.data.get(EVENT_START_DATETIME, dt_util.now())
    if EVENT_DURATION in service_call.data:
        end = start + service_call.data[EVENT_DURATION]
    else:
        end = service_call.data[EVENT_END_DATETIME]

    calendar_event_list = await calendar.async_get_events(
        calendar.hass, dt_util.as_local(start), dt_util.as_local(end)
    )
    return {
        "events": [
            dataclasses.asdict(event, dict_factory=list_events_dict_factory)
            for event in calendar_event_list
        ]
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the calendar services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        CREATE_EVENT_SERVICE,
        CREATE_EVENT_SCHEMA,
        async_create_event,
        required_features=[CalendarEntityFeature.CREATE_EVENT],
    )
    component.async_register_entity_service(
        SERVICE_GET_EVENTS,
        SERVICE_GET_EVENTS_SCHEMA,
        async_get_events_service,
        supports_response=SupportsResponse.ONLY,
    )
