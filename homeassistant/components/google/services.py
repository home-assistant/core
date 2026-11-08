"""Services for the Google Calendar integration."""

from datetime import timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, cast

from gcal_sync.exceptions import ApiException
from gcal_sync.model import DateOrDatetime, Event

from homeassistant.components.calendar import (
    CREATE_EVENT_SCHEMA,
    DOMAIN as CALENDAR_DOMAIN,
    CalendarEntityFeature,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import service
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_IN_DAYS, EVENT_IN_WEEKS
from .coordinator import CalendarSyncUpdateCoordinator

if TYPE_CHECKING:
    from .calendar import GoogleCalendarEntity


class GoogleCalendarService(StrEnum):
    """Store keys for Google Calendar services."""

    CREATE_EVENT = "create_event"


class GoogleCalendarServiceArgument(StrEnum):
    """Store keys for Google Calendar service arguments."""

    SUMMARY = "summary"
    DESCRIPTION = "description"
    START_DATE_TIME = "start_date_time"
    END_DATE_TIME = "end_date_time"
    START_DATE = "start_date"
    END_DATE = "end_date"
    IN = "in"
    LOCATION = "location"


async def async_create_event(entity: GoogleCalendarEntity, call: ServiceCall) -> None:
    """Add a new event to calendar."""
    start: DateOrDatetime | None = None
    end: DateOrDatetime | None = None
    hass = entity.hass

    if GoogleCalendarServiceArgument.IN in call.data:
        if EVENT_IN_DAYS in call.data[GoogleCalendarServiceArgument.IN]:
            today = dt_util.now().date()

            start_in = today + timedelta(
                days=call.data[GoogleCalendarServiceArgument.IN][EVENT_IN_DAYS]
            )
            end_in = start_in + timedelta(days=1)

            start = DateOrDatetime(date=start_in)
            end = DateOrDatetime(date=end_in)

        elif EVENT_IN_WEEKS in call.data[GoogleCalendarServiceArgument.IN]:
            today = dt_util.now().date()

            start_in = today + timedelta(
                weeks=call.data[GoogleCalendarServiceArgument.IN][EVENT_IN_WEEKS]
            )
            end_in = start_in + timedelta(days=1)

            start = DateOrDatetime(date=start_in)
            end = DateOrDatetime(date=end_in)

    elif (
        GoogleCalendarServiceArgument.START_DATE in call.data
        and GoogleCalendarServiceArgument.END_DATE in call.data
    ):
        start = DateOrDatetime(date=call.data[GoogleCalendarServiceArgument.START_DATE])
        end = DateOrDatetime(date=call.data[GoogleCalendarServiceArgument.END_DATE])

    elif (
        GoogleCalendarServiceArgument.START_DATE_TIME in call.data
        and GoogleCalendarServiceArgument.END_DATE_TIME in call.data
    ):
        start_dt = call.data[GoogleCalendarServiceArgument.START_DATE_TIME]
        end_dt = call.data[GoogleCalendarServiceArgument.END_DATE_TIME]
        start = DateOrDatetime(date_time=start_dt, timezone=str(hass.config.time_zone))
        end = DateOrDatetime(date_time=end_dt, timezone=str(hass.config.time_zone))

    if start is None or end is None:
        raise ValueError("Missing required fields to set start or end date/datetime")

    event = Event(
        summary=call.data[GoogleCalendarServiceArgument.SUMMARY],
        description=call.data[GoogleCalendarServiceArgument.DESCRIPTION],
        start=start,
        end=end,
    )
    if location := call.data.get(GoogleCalendarServiceArgument.LOCATION):
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
        GoogleCalendarService.CREATE_EVENT,
        entity_domain=CALENDAR_DOMAIN,
        schema=CREATE_EVENT_SCHEMA,
        func=async_create_event,
        required_features=[CalendarEntityFeature.CREATE_EVENT],
    )
