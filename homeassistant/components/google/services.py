"""Services for the Google Calendar integration."""

from datetime import timedelta
from typing import TYPE_CHECKING, cast

from gcal_sync.exceptions import ApiException
from gcal_sync.model import DateOrDatetime, Event

from homeassistant.components.calendar import (
    CREATE_EVENT_SCHEMA,
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_DESCRIPTION,
    EVENT_LOCATION,
    EVENT_SUMMARY,
    CalendarEntityFeature,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import service
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_END_DATE,
    EVENT_END_DATETIME,
    EVENT_IN,
    EVENT_IN_DAYS,
    EVENT_IN_WEEKS,
    EVENT_START_DATE,
    EVENT_START_DATETIME,
)
from .coordinator import CalendarSyncUpdateCoordinator

if TYPE_CHECKING:
    from .calendar import GoogleCalendarEntity

SERVICE_CREATE_EVENT = "create_event"


async def async_create_event(entity: GoogleCalendarEntity, call: ServiceCall) -> None:
    """Add a new event to calendar."""
    start: DateOrDatetime | None = None
    end: DateOrDatetime | None = None
    hass = entity.hass

    if EVENT_IN in call.data:
        if EVENT_IN_DAYS in call.data[EVENT_IN]:
            today = dt_util.now().date()

            start_in = today + timedelta(days=call.data[EVENT_IN][EVENT_IN_DAYS])
            end_in = start_in + timedelta(days=1)

            start = DateOrDatetime(date=start_in)
            end = DateOrDatetime(date=end_in)

        elif EVENT_IN_WEEKS in call.data[EVENT_IN]:
            today = dt_util.now().date()

            start_in = today + timedelta(weeks=call.data[EVENT_IN][EVENT_IN_WEEKS])
            end_in = start_in + timedelta(days=1)

            start = DateOrDatetime(date=start_in)
            end = DateOrDatetime(date=end_in)

    elif EVENT_START_DATE in call.data and EVENT_END_DATE in call.data:
        start = DateOrDatetime(date=call.data[EVENT_START_DATE])
        end = DateOrDatetime(date=call.data[EVENT_END_DATE])

    elif EVENT_START_DATETIME in call.data and EVENT_END_DATETIME in call.data:
        start_dt = call.data[EVENT_START_DATETIME]
        end_dt = call.data[EVENT_END_DATETIME]
        start = DateOrDatetime(date_time=start_dt, timezone=str(hass.config.time_zone))
        end = DateOrDatetime(date_time=end_dt, timezone=str(hass.config.time_zone))

    if start is None or end is None:
        raise ValueError("Missing required fields to set start or end date/datetime")

    event = Event(
        summary=call.data[EVENT_SUMMARY],
        description=call.data[EVENT_DESCRIPTION],
        start=start,
        end=end,
    )
    if location := call.data.get(EVENT_LOCATION):
        event.location = location
    try:
        await cast(
            CalendarSyncUpdateCoordinator, entity.coordinator
        ).sync.api.async_create_event(
            entity.calendar_id,
            event,
        )
    except ApiException as err:
        raise HomeAssistantError(str(err)) from err
    entity.async_write_ha_state()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Google Calendar integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CREATE_EVENT,
        entity_domain=CALENDAR_DOMAIN,
        schema=CREATE_EVENT_SCHEMA,
        func=async_create_event,
        required_features=[CalendarEntityFeature.CREATE_EVENT],
    )
