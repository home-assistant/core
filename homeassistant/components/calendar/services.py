"""Services for the calendar integration."""

import dataclasses
import datetime as dt
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
    DATA_COMPONENT,
    EVENT_END,
    EVENT_IN_DAYS,
    EVENT_IN_WEEKS,
    EVENT_START,
    EVENT_TIME_FIELDS,
    EVENT_TYPES,
    CalendarEntityFeature,
    CalendarService,
    CalendarServiceArgument,
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
    from .entity import CalendarEntity

CREATE_EVENT_SCHEMA = probatio.All(
    probatio.AtLeastOne(
        CalendarServiceArgument.START_DATE.value,
        CalendarServiceArgument.START_DATE_TIME.value,
        CalendarServiceArgument.IN.value,
    ),
    probatio.AtMostOne(
        CalendarServiceArgument.START_DATE.value,
        CalendarServiceArgument.START_DATE_TIME.value,
        CalendarServiceArgument.IN.value,
    ),
    cv.make_entity_service_schema(
        {
            probatio.Required(CalendarServiceArgument.SUMMARY): cv.string,
            probatio.Optional(
                CalendarServiceArgument.DESCRIPTION, default=""
            ): cv.string,
            probatio.Optional(CalendarServiceArgument.LOCATION): cv.string,
            probatio.Inclusive(
                CalendarServiceArgument.START_DATE,
                "dates",
                "Start and end dates must both be specified",
            ): cv.date,
            probatio.Inclusive(
                CalendarServiceArgument.END_DATE,
                "dates",
                "Start and end dates must both be specified",
            ): cv.date,
            probatio.Inclusive(
                CalendarServiceArgument.START_DATE_TIME,
                "datetimes",
                "Start and end datetimes must both be specified",
            ): cv.datetime,
            probatio.Inclusive(
                CalendarServiceArgument.END_DATE_TIME,
                "datetimes",
                "Start and end datetimes must both be specified",
            ): cv.datetime,
            probatio.Optional(CalendarServiceArgument.IN): probatio.Schema(
                {
                    probatio.Exclusive(EVENT_IN_DAYS, EVENT_TYPES): cv.positive_int,
                    probatio.Exclusive(EVENT_IN_WEEKS, EVENT_TYPES): cv.positive_int,
                }
            ),
        },
    ),
    has_consistent_timezone(
        CalendarServiceArgument.START_DATE_TIME, CalendarServiceArgument.END_DATE_TIME
    ),
    as_local_timezone(
        CalendarServiceArgument.START_DATE_TIME, CalendarServiceArgument.END_DATE_TIME
    ),
    has_min_duration(
        CalendarServiceArgument.START_DATE,
        CalendarServiceArgument.END_DATE,
        MIN_NEW_EVENT_DURATION,
    ),
    has_min_duration(
        CalendarServiceArgument.START_DATE_TIME,
        CalendarServiceArgument.END_DATE_TIME,
        MIN_NEW_EVENT_DURATION,
    ),
)


SERVICE_GET_EVENTS_SCHEMA: Final = probatio.All(
    probatio.AtLeastOne(
        CalendarServiceArgument.END_DATE_TIME.value,
        CalendarServiceArgument.DURATION.value,
    ),
    probatio.AtMostOne(
        CalendarServiceArgument.END_DATE_TIME.value,
        CalendarServiceArgument.DURATION.value,
    ),
    cv.make_entity_service_schema(
        {
            probatio.Optional(CalendarServiceArgument.START_DATE_TIME): cv.datetime,
            probatio.Optional(CalendarServiceArgument.END_DATE_TIME): cv.datetime,
            probatio.Optional(CalendarServiceArgument.DURATION): probatio.All(
                cv.time_period, cv.positive_timedelta
            ),
        }
    ),
    has_positive_interval(
        CalendarServiceArgument.START_DATE_TIME,
        CalendarServiceArgument.END_DATE_TIME,
        CalendarServiceArgument.DURATION,
    ),
)


def _validate_timespan(
    values: dict[str, Any],
) -> tuple[dt.datetime | dt.date, dt.datetime | dt.date]:
    """Parse a create event service call.

    Convert the args for a create event entity call.
    This converts the input service arguments into a
    `start` and `end` date or date time. This exists because
    service calls use `start_date` and `start_date_time`
    whereas the normal entity methods can take either a
    `datetime` or `date` as a single `start` argument.
    It also handles the other service call variations like "in days" as well.
    """

    if event_in := values.get(CalendarServiceArgument.IN):
        days = event_in.get(EVENT_IN_DAYS, 7 * event_in.get(EVENT_IN_WEEKS, 0))
        today = dt_util.now().date()
        return (
            today + dt.timedelta(days=days),
            today + dt.timedelta(days=days + 1),
        )

    if (
        CalendarServiceArgument.START_DATE in values
        and CalendarServiceArgument.END_DATE in values
    ):
        return (
            values[CalendarServiceArgument.START_DATE],
            values[CalendarServiceArgument.END_DATE],
        )

    if (
        CalendarServiceArgument.START_DATE_TIME in values
        and CalendarServiceArgument.END_DATE_TIME in values
    ):
        return (
            values[CalendarServiceArgument.START_DATE_TIME],
            values[CalendarServiceArgument.END_DATE_TIME],
        )

    raise ValueError("Missing required fields to set start or end date/datetime")


async def _async_create_event(entity: CalendarEntity, call: ServiceCall) -> None:
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
    start = service_call.data.get(
        CalendarServiceArgument.START_DATE_TIME, dt_util.now()
    )
    if CalendarServiceArgument.DURATION in service_call.data:
        end = start + service_call.data[CalendarServiceArgument.DURATION]
    else:
        end = service_call.data[CalendarServiceArgument.END_DATE_TIME]

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
        CalendarService.CREATE_EVENT,
        CREATE_EVENT_SCHEMA,
        _async_create_event,
        required_features=[CalendarEntityFeature.CREATE_EVENT],
    )
    component.async_register_entity_service(
        CalendarService.GET_EVENTS,
        SERVICE_GET_EVENTS_SCHEMA,
        async_get_events_service,
        supports_response=SupportsResponse.ONLY,
    )
