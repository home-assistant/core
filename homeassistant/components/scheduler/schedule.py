"""Define the scheduler object and its associated schedule objects."""
from datetime import datetime, timedelta
import logging
from typing import Awaitable, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from dateutil.rrule import rrule, rrulestr

from homeassistant.const import CONF_ENTITY_ID, MATCH_ALL
from homeassistant.core import Context, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change,
)
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)
DOMAIN = "scheduler"

STORAGE_VERSION = 1

CONF_END_DATETIME = "end_datetime"
CONF_RECURRENCE = "recurrence"
CONF_SCHEDULE_ID = "schedule_id"
CONF_START_DATETIME = "start_datetime"


class ScheduleInstance:
    """A class to represent an active instance of a schedule."""

    def __init__(self, hass: HomeAssistant, entity_id: str):
        """Initialize."""
        self._affected_states: List[State] = []
        self._async_state_listener: Optional[Callable[..., Awaitable]] = None
        self._context = Context()
        self._hass = hass
        self.entity_id = entity_id

    @callback
    def async_cancel(self) -> None:
        """Cancel the instance."""
        if self._async_state_listener:
            self._async_state_listener()
            self._async_state_listener = None

    async def async_revert(self) -> None:
        """Restore the entities touched by the schedule."""
        if not self._affected_states:
            return

        entities = {}
        for state in self._affected_states:
            data = {**state.attributes}
            data["state"] = state.state
            entities[state.entity_id] = data

        await self._hass.services.async_call(
            "scene",
            "apply",
            service_data={"entities": entities},
            blocking=True,
            context=self._context,
        )

        _LOGGER.info("Scheduler reverted scene: %s", self.entity_id)

    async def async_trigger(self) -> None:
        """Trigger the schedule's scene."""

        @callback
        def store_entity_if_in_context(
            entity_id: str, old_state: State, new_state: State
        ) -> None:
            """Save prior states of an entity if it was triggered by this schedule."""
            if new_state.context == self._context:
                self._affected_states.append(old_state)

        self._async_state_listener = async_track_state_change(
            self._hass, MATCH_ALL, store_entity_if_in_context
        )

        await self._hass.services.async_call(
            "scene",
            "turn_on",
            service_data={"entity_id": self.entity_id},
            blocking=True,
            context=self._context,
        )

        _LOGGER.info("Scheduler triggered scene: %s", self.entity_id)


class Schedule:
    """A class to represent a schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        start_datetime: datetime,
        *,
        end_datetime: Optional[datetime] = None,
        recurrence: Optional[rrule] = None,
    ):
        """Initialize."""
        self._async_revert_listener: Optional[Callable[..., Awaitable]] = None
        self._async_trigger_listener: Optional[Callable[..., Awaitable]] = None
        self._hass: HomeAssistant = hass
        self._initial_instance_scheduled: bool = False
        self.active_instance: Optional[ScheduleInstance] = None
        self.end_datetime: Optional[datetime] = end_datetime
        self.entity_id: str = entity_id
        self.recurrence: Optional[rrule] = recurrence
        self.schedule_id: str = uuid4().hex
        self.start_datetime: datetime = start_datetime

        self.instance_duration: Optional[timedelta]
        if self.end_datetime:
            self.instance_duration = self.end_datetime - self.start_datetime
        else:
            self.instance_duration = None

    def __str__(self) -> str:
        """Define the string representation of this schedule."""
        return (
            f'<Schedule start="{self.start_datetime}" '
            f'end="{self.end_datetime}" rrule="{self.recurrence}">'
        )

    @property
    def active(self) -> bool:
        """Return whether the schedule has an active instance."""
        # Instances with no end datetimes are one-shots and are not active:
        if not self.end_datetime:
            return False

        now = dt_util.utcnow()

        # If we're between the initial start and the end time, we're active:
        if self.start_datetime <= now <= self.end_datetime:
            return True

        # Otherwise, look at the recurrence (specifically, the datetime just before
        # now) and see if we're still within it:
        last_start_dt = self.recurrence.before(now, inc=True)
        last_end_dt = last_start_dt + self.instance_duration
        return last_start_dt <= now <= last_end_dt

    @property
    def expired(self) -> bool:
        """Return whether the schedule has expired."""
        now = dt_util.utcnow()
        return (
            self.end_datetime and self.end_datetime < now
        ) or self.start_datetime < now

    @callback
    def _get_next_datetimes(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Get the next starting (and, optionally, ending) datetimes."""
        if not self._initial_instance_scheduled:
            self._initial_instance_scheduled = True
            return (self.start_datetime, self.end_datetime)

        if self.recurrence:
            start = self.recurrence.after(dt_util.utcnow(), inc=True)
            if self.end_datetime:
                end = start + self.instance_duration
            else:
                end = None
            return (start, end)

        return (None, None)

    def as_dict(self) -> dict:
        """Return the schedule as a dict."""
        the_dict = {
            CONF_ENTITY_ID: self.entity_id,
            CONF_START_DATETIME: self.start_datetime.isoformat(),
        }

        if self.end_datetime:
            the_dict[CONF_END_DATETIME] = self.end_datetime.isoformat()
        else:
            the_dict[CONF_END_DATETIME] = None

        if self.recurrence:
            the_dict[CONF_RECURRENCE] = str(self.recurrence)
        else:
            the_dict[CONF_RECURRENCE] = None

        return the_dict

    @callback
    def async_cancel(self) -> None:
        """Cancel the schedule."""
        self.active_instance.async_cancel()
        self.active_instance = None

        if self._async_revert_listener:
            self._async_revert_listener()
            self._async_revert_listener = None
        if self._async_trigger_listener:
            self._async_trigger_listener()
            self._async_trigger_listener = None

    @callback
    def async_schedule(self) -> None:
        """Schedule the next instance."""
        start_dt, end_dt = self._get_next_datetimes()

        if not start_dt:
            _LOGGER.info("No more instances of schedule: %s", self)
            return

        self.active_instance = ScheduleInstance(self._hass, self.entity_id)

        async def trigger(self, executed_at: datetime) -> None:
            """Trigger when the schedule starts."""
            await self.active_instance.async_trigger()
            if not self.end_datetime:
                await self.async_schedule()

        async def revert(self, executed_at: datetime) -> None:
            """Trigger when the schedule ends."""
            await self.active_instance.async_revert()
            await self.async_schedule()

        self._async_trigger_listener = async_track_point_in_time(
            self._hass, trigger, start_dt
        )

        if end_dt:
            self._async_trigger_listener = async_track_point_in_time(
                self._hass, revert, end_dt
            )


class Scheduler:
    """A class to represent the scheduler."""

    def __init__(self, hass: HomeAssistant):
        """Initialize."""
        self._hass: HomeAssistant = hass
        self._store: Store = Store(hass, STORAGE_VERSION, DOMAIN)
        self.schedules: Dict[str, Schedule] = {}

    @callback
    def async_create(self, schedule: Schedule) -> None:
        """Create a schedule."""
        self.schedules[schedule.schedule_id] = schedule
        self.schedules[schedule.schedule_id].async_schedule()

    @callback
    def async_delete(self, schedule_id: str) -> None:
        """Delete a schedule."""
        schedule = self.schedules.pop(schedule_id)
        schedule.async_cancel()

    async def async_load(self) -> None:
        """Load all schedules from storage."""
        raw_schedules = await self._store.async_load()

        if not raw_schedules:
            return

        self.schedules = []
        for schedule_id, schedule_dict in raw_schedules.items():
            if schedule_dict.get(CONF_END_DATETIME):
                end_dt = dt_util.parse_datetime(schedule_dict[CONF_END_DATETIME])
            else:
                end_dt = None

            if schedule_dict.get(CONF_RECURRENCE):
                recurrence = rrulestr(schedule_dict[CONF_RECURRENCE])
            else:
                recurrence = None

            schedule = Schedule(
                self._hass,
                schedule_dict[CONF_ENTITY_ID],
                dt_util.parse_datetime(schedule_dict[CONF_START_DATETIME]),
                end_datetime=end_dt,
                recurrence=recurrence,
            )

            schedule.schedule_id = schedule_id
            self.async_create(schedule)

    async def async_save(self) -> None:
        """Save all schedules to storage."""
        await self._store.async_save(
            {
                schedule_id: schedule.as_dict()
                for schedule_id, schedule in self.schedules.items()
            }
        )

    @callback
    def async_update(self, schedule_id: str, new_schedule: Schedule) -> None:
        """Update a schedule."""
        self.schedules[schedule_id].async_cancel()
        new_schedule.schedule_id = schedule_id
        self.schedules[schedule_id] = new_schedule
        self.schedules[schedule_id].async_schedule()
