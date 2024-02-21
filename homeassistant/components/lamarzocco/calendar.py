"""Calendar platform for La Marzocco espresso machines."""
from collections.abc import Callable, Coroutine, Iterator
from datetime import datetime, time, timedelta
import logging
from typing import Any, Final

from lmcloud.exceptions import AuthFail, RequestNotSuccessful
import voluptuous as vol

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import LaMarzoccoBaseEntity

_LOGGER = logging.getLogger(__name__)


CALENDAR_KEY: Final = "auto_on_off_schedule"
SERVICE_AUTO_ON_OFF_ENABLE: Final = "set_auto_on_off_enable"
SERVICE_AUTO_ON_OFF_TIMES: Final = "set_auto_on_off_times"

ATTR_DAY_OF_WEEK: Final = "day_of_week"
ATTR_ENABLE: Final = "enable"
ATTR_TIME_ON: Final = "time_on"
ATTR_TIME_OFF: Final = "time_off"

OPTIONS_DAY_OF_WEEK: Final = (
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
)
=======
CALENDAR_KEY = "auto_on_off_schedule"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities and services."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([LaMarzoccoCalendarEntity(coordinator, CALENDAR_KEY)])

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_AUTO_ON_OFF_ENABLE,
        {
            vol.Required(ATTR_DAY_OF_WEEK): vol.In(OPTIONS_DAY_OF_WEEK),
            vol.Required(ATTR_ENABLE): cv.boolean,
        },
        "set_auto_on_off_enable",
    )

    platform.async_register_entity_service(
        SERVICE_AUTO_ON_OFF_TIMES,
        {
            vol.Required(ATTR_DAY_OF_WEEK): vol.In(OPTIONS_DAY_OF_WEEK),
            vol.Required(ATTR_TIME_ON): cv.time,
            vol.Required(ATTR_TIME_OFF): cv.time,
            vol.Optional(ATTR_ENABLE): cv.boolean,
        },
        "set_auto_on_off_times",
    )


class LaMarzoccoCalendarEntity(LaMarzoccoBaseEntity, CalendarEntity):
    """Class representing a La Marzocco calendar."""

    _attr_translation_key = CALENDAR_KEY

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()

        events = self._get_events(
            start_date=now,
            end_date=now + timedelta(days=7),  # only need to check a week ahead
        )
        return next(iter(events), None)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""

        return self._get_events(
            start_date=start_date,
            end_date=end_date,
        )

    def _get_events(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Get calendar events within a datetime range."""

        events: list[CalendarEvent] = []
        for date in self._get_date_range(start_date, end_date):
            if scheduled := self._async_get_calendar_event(date):
                if scheduled.end < start_date:
                    continue
                if scheduled.start > end_date:
                    continue
                events.append(scheduled)
        return events

    def _get_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> Iterator[datetime]:
        current_date = start_date
        
        while current_date.date() < end_date.date():
            yield current_date
            current_date += timedelta(days=1)
        yield end_date

    def _async_get_calendar_event(self, date: datetime) -> CalendarEvent | None:
        """Return calendar event for a given weekday."""

        # check first if auto/on off is turned on in general
        # because could still be on for that day but disabled
        if self.coordinator.lm.current_status["global_auto"] != "Enabled":
            return None

        # parse the schedule for the day
        schedule_day = self.coordinator.lm.schedule[date.weekday()]
        if schedule_day["enable"] == "Disabled":
            return None
        hour_on, minute_on = schedule_day["on"].split(":")
        hour_off, minute_off = schedule_day["off"].split(":")
        return CalendarEvent(
            start=date.replace(
                hour=int(hour_on),
                minute=int(minute_on),
                second=0,
                microsecond=0,
            ),
            end=date.replace(
                hour=int(hour_off),
                minute=int(minute_off),
                second=0,
                microsecond=0,
            ),

            summary=f"Machine {self.coordinator.config_entry.title} on",
            description="Machine is scheduled to turn on at the start time and off at the end time",
        )

    async def _call_service(
        self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any
    ) -> None:
        """Call a service and handle exceptions."""
        try:
            await func(*args, **kwargs)
        except (AuthFail, RequestNotSuccessful, TimeoutError) as exc:
            raise HomeAssistantError(
                f"Service call encountered an error: {exc}",
                translation_key="service_error",
                translation_placeholders={"error": str(exc)},
            ) from exc

    async def set_auto_on_off_enable(self, day_of_week: str, enable: bool) -> None:
        """Service call to enable auto on/off."""

        _LOGGER.debug("Setting auto on/off for %s to %s", day_of_week, enable)
        await self._call_service(
            self.coordinator.lm.set_auto_on_off_enable,
            day_of_week=day_of_week,
            enable=enable,
        )

    async def set_auto_on_off_times(
        self,
        day_of_week: str,
        time_on: time,
        time_off: time,
        enable: bool | None = None,
    ) -> None:
        """Service call to configure auto on/off hours for a day."""

        if enable is not None:
            await self.set_auto_on_off_enable(day_of_week, enable)

        _LOGGER.debug(
            "Setting auto on/off hours for %s from %s to %s",
            day_of_week,
            time_on,
            time_off,
        )
        await self._call_service(
            self.coordinator.lm.set_auto_on_off,
            day_of_week=day_of_week,
            hour_on=time_on.hour,
            minute_on=time_on.minute,
            hour_off=time_off.hour,
            minute_off=time_off.minute,
        )
