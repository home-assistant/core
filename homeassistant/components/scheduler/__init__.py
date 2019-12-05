"""Support for scheduling scenes."""
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from uuid import uuid4

from dateutil.rrule import rrule, rrulestr
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ENTITY_ID, CONF_ID, MATCH_ALL
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change,
)
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)
DOMAIN = "scheduler"

STORAGE_VERSION = 1

CONF_ACTIVATION_CONTEXT = "activation_context"
CONF_ACTIVATION_CONTEXT_ID = "activation_context_id"
CONF_END_DATETIME = "end_datetime"
CONF_RRULE = "rrule"
CONF_SCHEDULE_ID = "schedule_id"
CONF_START_DATETIME = "start_datetime"

SCHEDULE_UPDATE_SCHEMA = vol.Schema(
    {
        CONF_ENTITY_ID: cv.entity_id,
        CONF_START_DATETIME: cv.datetime,
        CONF_END_DATETIME: cv.datetime,
        CONF_RRULE: str,
    }
)


async def async_setup(hass, config):
    """Set up the scheduler."""
    if DOMAIN not in config:
        return True

    scheduler = hass.data[DOMAIN] = Scheduler(hass)
    await scheduler.async_load()

    hass.components.websocket_api.async_register_command(
        async_websocket_handle_clear_expired
    )
    hass.components.websocket_api.async_register_command(async_websocket_handle_create)
    hass.components.websocket_api.async_register_command(async_websocket_handle_delete)
    hass.components.websocket_api.async_register_command(async_websocket_handle_list)
    hass.components.websocket_api.async_register_command(async_websocket_handle_update)

    return True


class ActiveScheduleInstance:
    """A class that defines a scene schedule."""

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Initialize."""
        self._async_state_listener: Optional[CALLBACK_TYPE] = None
        self._context: Context = Context()
        self._affected_states: List[State] = []
        self._hass: HomeAssistant = hass
        self.entity_id: str = entity_id
        self.instance_id = uuid4().hex

    async def async_trigger_scene(self) -> None:
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

        _LOGGER.info("Scheduler activated scene: %s", self.entity_id)

    async def async_undo_scene(self) -> None:
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

        _LOGGER.info("Scheduler deactivated scene: %s", self.entity_id)


class Schedule:
    """A class to define an individual schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        schedule_id: str,
        entity_id: str,
        start_datetime: datetime,
        *,
        end_datetime: Optional[datetime] = None,
        rrule_str: Optional[str] = None,
    ) -> None:
        """Initialize."""
        self._async_activation_listener: Optional[CALLBACK_TYPE] = None
        self._async_deactivation_listener: Optional[CALLBACK_TYPE] = None
        self._current_instance: Optional[ActiveScheduleInstance] = None
        self._hass: HomeAssistant = hass
        self._initial_run_complete: bool = False
        self.entity_id = entity_id
        self.schedule_id: str = schedule_id

        self.start_datetime: datetime = start_datetime
        self.end_datetime: Optional[datetime] = end_datetime

        self._duration: Optional[timedelta]
        if self.end_datetime:
            self._duration = self.end_datetime - self.start_datetime
        else:
            self._duration = None

        self.rrule: Optional[rrule]
        if rrule_str:
            self.rrule = rrulestr(rrule_str)
        else:
            self.rrule = None

    def __str__(self) -> str:
        """Define the string representation of this schedule."""
        return (
            f'<Schedule start="{self.start_datetime}" '
            f'end="{self.end_datetime}" rrule="{self.rrule}">'
        )

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

        if self.rrule:
            the_dict[CONF_RRULE] = str(self.rrule)
        else:
            the_dict[CONF_RRULE] = None

        return the_dict

    async def async_cancel_current_instance(self) -> None:
        """Delete the latest (active) instance of a schedule."""
        await self._current_instance.async_undo_scene()
        self._current_instance = None

        if self._async_activation_listener:
            self._async_activation_listener()
            self._async_activation_listener = None
        if self._async_deactivation_listener:
            self._async_deactivation_listener()
            self._async_deactivation_listener = None

    async def async_schedule_next_instance(self) -> None:
        """Schedule the next instance of a schedule."""
        start_dt: Optional[datetime] = None
        if not self._initial_run_complete:
            self._initial_run_complete = True
            start_dt = self.start_datetime
            end_dt = self.end_datetime
        elif self.rrule:
            start_dt = self.rrule.after(datetime.now(), inc=True)
            end_dt = start_dt + self._duration

        if not start_dt:
            return

        instance: ActiveScheduleInstance = ActiveScheduleInstance(
            self._hass, self.entity_id
        )

        async def schedule_start(executed_at: datetime) -> None:
            """Trigger when the schedule starts."""
            await instance.async_trigger_scene()
            if not end_dt:
                await self.async_schedule_next_instance()

        async def schedule_end(executed_at: datetime) -> None:
            """Trigger when the schedule ends."""
            await instance.async_undo_scene()
            await self.async_schedule_next_instance()

        self._async_activation_listener = async_track_point_in_time(
            self._hass, schedule_start, start_dt
        )
        if end_dt:
            self._async_deactivation_listener = async_track_point_in_time(
                self._hass, schedule_end, end_dt
            )

        self._current_instance = instance

        _LOGGER.info(
            "Scheduled instance of schedule %s (start: %s / end: %s)",
            self,
            start_dt,
            end_dt,
        )


class Scheduler:
    """A class to manage scene schedules."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._hass: HomeAssistant = hass
        self._latest_instances: List[ActiveScheduleInstance] = []
        self._store = Store(hass, STORAGE_VERSION, DOMAIN)
        self.schedules: Dict[str, Schedule] = {}

    async def async_clear_expired_schedules(self) -> None:
        """Delete expired schedules."""
        now = datetime.now()
        self.schedules = {
            schedule_id: schedule
            for schedule_id, schedule in self.schedules.items()
            if (not schedule.end_datetime and schedule.start_datetime < now)
            or (schedule.end_datetime and schedule.end_datetime < now)
        }

        await self.async_save()

    async def async_create(
        self,
        entity_id: str,
        start_datetime: datetime,
        *,
        end_datetime: Optional[datetime] = None,
        rrule_str: Optional[str] = None,
        schedule_id: Optional[str] = None,
    ) -> dict:
        """Create a schedule.

        The rrule_str parameter must be an RFC5545-compliant string.
        """
        if not schedule_id:
            schedule_id = uuid4().hex
        schedule = Schedule(
            self._hass,
            schedule_id,
            entity_id,
            start_datetime,
            end_datetime=end_datetime,
            rrule_str=rrule_str,
        )

        self.schedules[schedule_id] = schedule
        await self.async_save()
        _LOGGER.info("Created schedule: %s", schedule)

        await schedule.async_schedule_next_instance()

        return schedule.as_dict()

    async def async_delete(self, schedule_id: str, *, save: bool = True) -> dict:
        """Delete a schedule."""
        if schedule_id not in self.schedules:
            raise KeyError

        schedule = self.schedules.pop(schedule_id)
        await schedule.async_cancel_current_instance()

        if save:
            await self.async_save()

        _LOGGER.info('Deleted schedule "%s"', schedule)
        return schedule.as_dict()

    async def async_load(self) -> None:
        """Load all schedules from storage."""

        raw_schedules = await self._store.async_load()

        if not raw_schedules:
            return

        tasks = []
        for schedule_id, schedule in raw_schedules.items():
            if schedule.get(CONF_END_DATETIME):
                end_dt = dt_util.parse_datetime(schedule[CONF_END_DATETIME])
            else:
                end_dt = None
            tasks.append(
                self.async_create(
                    schedule[CONF_ENTITY_ID],
                    dt_util.parse_datetime(schedule[CONF_START_DATETIME]),
                    end_datetime=end_dt,
                    rrule_str=schedule.get(CONF_RRULE),
                    schedule_id=schedule_id,
                )
            )

        await asyncio.gather(*tasks)

    async def async_save(self) -> None:
        """Save all schedules to storage."""
        await self._store.async_save(
            {
                schedule_id: schedule.as_dict()
                for schedule_id, schedule in self.schedules.items()
            }
        )

    async def async_update(self, schedule_id: str, new_data: dict) -> dict:
        """Update a schedule."""
        if schedule_id not in self.schedules:
            raise KeyError

        new_data = SCHEDULE_UPDATE_SCHEMA(new_data)
        data = await self.async_delete(schedule_id, save=False)
        data.update(new_data)
        return self.async_create(
            data[CONF_ENTITY_ID],
            data[CONF_START_DATETIME],
            end_datetime=data[CONF_END_DATETIME],
            rrule_str=data[CONF_RRULE],
            schedule_id=schedule_id,
        )


@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required("type"): "scheduler/schedules/clear_expired"}
)
async def async_websocket_handle_clear_expired(hass, connection, msg):
    """Handle clearing expired schedules."""
    await hass.data[DOMAIN].async_clear_expired_schedules()
    connection.send_message(
        websocket_api.result_message(msg[CONF_ID], hass.data[DOMAIN].schedules)
    )


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "scheduler/schedules/create",
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_START_DATETIME): cv.datetime,
        vol.Optional(CONF_END_DATETIME): cv.datetime,
        vol.Optional(CONF_RRULE): str,
    }
)
async def async_websocket_handle_create(hass, connection, msg):
    """Handle creating a schedule."""
    schedule = await hass.data[DOMAIN].async_create(
        msg[CONF_ENTITY_ID],
        msg[CONF_START_DATETIME],
        end_datetime=msg.get(CONF_END_DATETIME),
        rrule_str=msg.get(CONF_RRULE),
    )
    connection.send_message(websocket_api.result_message(msg[CONF_ID], schedule))


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "scheduler/schedules/delete",
        vol.Required(CONF_SCHEDULE_ID): str,
    }
)
async def async_websocket_handle_delete(hass, connection, msg):
    """Handle deleting a schedule."""
    try:
        schedule = await hass.data[DOMAIN].async_delete(msg[CONF_SCHEDULE_ID])
    except KeyError:
        connection.send_message(
            websocket_api.error_message(
                msg[CONF_ID],
                "schedule_not_found",
                f"Cannot delete unknown schedule ID: {msg[CONF_SCHEDULE_ID]}",
            )
        )
    else:
        connection.send_message(websocket_api.result_message(msg[CONF_ID], schedule))


@callback
@websocket_api.websocket_command({vol.Required("type"): "scheduler/schedules/list"})
def async_websocket_handle_list(hass, connection, msg):
    """Handle getting all schedules."""
    connection.send_message(
        websocket_api.result_message(msg[CONF_ID], hass.data[DOMAIN].schedules)
    )


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "scheduler/schedules/update",
        vol.Required(CONF_SCHEDULE_ID): str,
        vol.Optional(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_START_DATETIME): cv.datetime,
        vol.Optional(CONF_END_DATETIME): cv.datetime,
        vol.Optional(CONF_RRULE): str,
    }
)
async def async_websocket_handle_update(hass, connection, msg):
    """Handle updating a schedule."""
    msg_id = msg.pop("id")
    msg.pop("type")
    schedule_id = msg.pop("schedule_id")
    data = msg

    try:
        schedule = await hass.data[DOMAIN].async_update(schedule_id, data)
    except KeyError:
        connection.send_message(
            websocket_api.error_message(
                msg[CONF_ID],
                "schedule_not_found",
                f"Cannot update unknown schedule ID: {msg[CONF_SCHEDULE_ID]}",
            )
        )
    else:
        connection.send_message(websocket_api.result_message(msg_id, schedule))
