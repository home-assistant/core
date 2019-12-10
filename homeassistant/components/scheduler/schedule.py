"""Define the scheduler object and its associated schedule objects."""
from datetime import datetime
import logging
from typing import Awaitable, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from dateutil.rrule import rrule, rrulestr

from homeassistant.const import CONF_ENTITY_ID, MATCH_ALL, STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
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

STATE_EXPIRED = "expired"

TOPIC_SCHEDULE_NEXT = "scheduler_schedule_next"


class ScheduleInstance:
    """A class to represent an active instance of a schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        start_datetime: datetime,
        end_datetime: Optional[datetime] = None,
    ):
        """Initialize."""
        self._affected_states: List[State] = []
        self._async_revert_listener: Optional[Callable[..., Awaitable]] = None
        self._async_state_listener: Optional[Callable[..., Awaitable]] = None
        self._async_trigger_listener: Optional[Callable[..., Awaitable]] = None
        self._context: Context = Context()
        self._hass: HomeAssistant = hass
        self.end_datetime: Optional[datetime] = end_datetime
        self.entity_id: str = entity_id
        self.start_datetime: datetime = start_datetime

    @callback
    def async_init(self) -> None:
        """Set up scheduling for this instance."""

        async def revert(executed_at: datetime) -> None:
            """Revert."""
            await self.async_revert()

        async def trigger(executed_at: datetime) -> None:
            """Trigger."""
            await self.async_trigger()

        self._async_trigger_listener = async_track_point_in_time(
            self._hass, trigger, self.start_datetime
        )

        if self.end_datetime:
            self._async_trigger_listener = async_track_point_in_time(
                self._hass, revert, self.end_datetime
            )

    @callback
    def async_cancel(self) -> None:
        """Cancel the instance."""
        if self._async_revert_listener:
            self._async_revert_listener()
            self._async_revert_listener = None
        if self._async_state_listener:
            self._async_state_listener()
            self._async_state_listener = None
        if self._async_trigger_listener:
            self._async_trigger_listener()
            self._async_trigger_listener = None

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

        async_dispatcher_send(self._hass, TOPIC_SCHEDULE_NEXT)

    async def async_trigger(self) -> None:
        """Trigger the schedule's scene."""

        @callback
        def store_entity_if_in_context(
            entity_id: str, old_state: State, new_state: State
        ) -> None:
            """Save prior states of an entity if it was triggered by this schedule."""
            if new_state.context == self._context:
                self._affected_states.append(old_state)

        if self.end_datetime:
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

        if not self.end_datetime:
            async_dispatcher_send(self._hass, TOPIC_SCHEDULE_NEXT)


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
        self._async_unsub_dispatcher_connect: Optional[Callable[..., Awaitable]] = None
        self._hass: HomeAssistant = hass
        self._initial_instance_scheduled: bool = False
        self._is_on: bool = False
        self.active_instance: Optional[ScheduleInstance] = None
        self.end_datetime: Optional[datetime] = end_datetime
        self.entity_id: str = entity_id
        self.recurrence: Optional[rrule] = recurrence
        self.schedule_id: str = uuid4().hex
        self.start_datetime: datetime = start_datetime

    def __str__(self) -> str:
        """Define the string representation of this schedule."""
        return (
            f'<Schedule start="{self.start_datetime}" '
            f'end="{self.end_datetime}" rrule="{self.recurrence}">'
        )

    @property
    def active(self) -> bool:
        """Return whether the schedule has an active instance."""
        return self.active_instance is not None

    @property
    def expired(self) -> bool:
        """Return whether the schedule has expired."""
        now = dt_util.utcnow()

        # If a recurrence exists and there's at least one instance of it in the future,
        # we're not expired:
        if self.recurrence and self.recurrence.after(now, inc=True):
            return False

        # If either the initial start datetime or the end datetime (if it exists) are in
        # in the future, we're not expired:
        if self.start_datetime >= now or (
            self.end_datetime and self.end_datetime >= now
        ):
            return False

        return True

    @property
    def state(self) -> str:
        """Return the current state of the schdule."""
        if self.expired:
            return STATE_EXPIRED
        if self.is_on:
            return STATE_ON
        return STATE_OFF

    @property
    def is_on(self) -> bool:
        """Return whether the schedule is turned on.

        Schedules are off until specifically turned on via async_turn_on().
        """
        return self._is_on

    @callback
    def _async_schedule(self) -> None:
        """Schedule the next instance."""
        if not self.is_on:
            _LOGGER.warning("Schedule is turned off")
            return

        start_dt, end_dt = self._get_next_instance_datetimes()

        if not start_dt:
            _LOGGER.info("No more instances of schedule: %s", self)
            self.active_instance = None
            return

        instance = ScheduleInstance(self._hass, self.entity_id, start_dt, end_dt)
        instance.async_init()

        if self.end_datetime:
            self.active_instance = instance
        else:
            self.active_instance = None

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self._hass, TOPIC_SCHEDULE_NEXT, self._async_schedule
        )

    @callback
    def _get_next_instance_datetimes(
        self,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Get the next starting (and, optionally, ending) datetimes."""
        if not self._initial_instance_scheduled:
            self._initial_instance_scheduled = True
            return (self.start_datetime, self.end_datetime)

        if not self.recurrence:
            return (None, None)

        start = self.recurrence.after(dt_util.utcnow(), inc=True)

        # The recurrence has reached its end:
        if not start:
            return (None, None)

        if self.end_datetime:
            end = start + (self.end_datetime - self.start_datetime)
        else:
            end = None

        return (start, end)

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
    def async_turn_off(self) -> None:
        """Disable the schedule."""
        if self.active_instance:
            self.active_instance.async_cancel()
            self.active_instance = None

        self._is_on = False

    @callback
    def async_turn_on(self) -> None:
        """Enable the schedule."""
        if self.expired:
            raise ValueError("Cannot turn on expired schedule")

        self._is_on = True
        self._async_schedule()


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
        schedule.async_turn_on()
        self.schedules[schedule.schedule_id] = schedule

    @callback
    def async_delete(self, schedule_id: str) -> None:
        """Delete a schedule."""
        schedule = self.schedules.pop(schedule_id)
        schedule.turn_off()

    async def async_load(self) -> None:
        """Load all schedules from storage."""
        raw_schedules = await self._store.async_load()

        if not raw_schedules:
            return

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
        new_schedule.async_schedule()
        self.schedules[schedule_id] = new_schedule
