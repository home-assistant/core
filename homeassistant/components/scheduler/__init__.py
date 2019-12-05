"""Support for scheduling scenes."""
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Callable, Dict, List, Optional
from uuid import uuid4

from dateutil.rrule import rrulestr
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ENTITY_ID, CONF_ID, MATCH_ALL
from homeassistant.core import Context, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change,
)
import homeassistant.util.dt as dt_util
from homeassistant.util.json import load_json, save_json

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall, State  # noqa

_LOGGER = logging.getLogger(__name__)
DOMAIN = "scheduler"

PERSISTENCE = ".scheduler.json"
EVENT = "scheduler_updated"

CONF_ACTIVATION_CONTEXT = "activation_context"
CONF_ACTIVATION_CONTEXT_ID = "activation_context_id"
CONF_DURATION = "duration"
CONF_END_DATETIME = "end_datetime"
CONF_RRULE = "rrule"
CONF_SCHEDULE_ID = "schedule_id"
CONF_START_DATETIME = "start_datetime"

SCHEDULE_UPDATE_SCHEMA = vol.All(
    vol.Schema({CONF_ENTITY_ID: cv.entity_id, CONF_DURATION: int, CONF_RRULE: str}),
    cv.has_at_least_one_key(CONF_ENTITY_ID, CONF_DURATION, CONF_RRULE),
)

WS_TYPE_SCHEDULER_CREATE_SCHEDULE = "scheduler/schedules/create"
WS_TYPE_SCHEDULER_DELETE_SCHEDULE = "scheduler/schedules/delete"
WS_TYPE_SCHEDULER_SCHEDULES = "scheduler/schedules"
WS_TYPE_SCHEDULER_UPDATE_SCHEDULE = "scheduler/schedules/update"

SCHEMA_WEBSOCKET_CREATE_SCHEDULE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_CREATE_SCHEDULE,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_START_DATETIME): cv.datetime,
        vol.Optional(CONF_RRULE): str,
        vol.Optional(CONF_DURATION): int,
    }
)

SCHEMA_WEBSOCKET_DELETE_SCHEDULE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_DELETE_SCHEDULE,
        vol.Required(CONF_SCHEDULE_ID): str,
    }
)

SCHEMA_WEBSOCKET_SCHEDULES = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_SCHEDULER_SCHEDULES}
)

SCHEMA_WEBSOCKET_UPDATE_SCHEDULE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_UPDATE_SCHEDULE,
        vol.Required(CONF_SCHEDULE_ID): str,
        vol.Optional(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_START_DATETIME): cv.datetime,
        vol.Optional(CONF_DURATION): int,
        vol.Optional(CONF_RRULE): str,
    }
)


async def async_setup(hass, config):
    """Set up the scheduler."""
    if DOMAIN not in config:
        return True

    scheduler = hass.data[DOMAIN] = Scheduler(hass)
    await scheduler.async_load()

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_CREATE_SCHEDULE,
        websocket_handle_create,
        SCHEMA_WEBSOCKET_CREATE_SCHEDULE,
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_DELETE_SCHEDULE,
        websocket_handle_delete,
        SCHEMA_WEBSOCKET_DELETE_SCHEDULE,
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_SCHEDULES,
        websocket_handle_schedules,
        SCHEMA_WEBSOCKET_SCHEDULES,
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_UPDATE_SCHEDULE,
        websocket_handle_update,
        SCHEMA_WEBSOCKET_UPDATE_SCHEDULE,
    )

    return True


class ScheduleInstance:
    """A class that defines a scene schedule."""

    def __init__(
        self, hass: "HomeAssistant", entity_id: str, activation_context: Context,
    ) -> None:
        """Initialize."""
        self._activation_context = activation_context
        self._async_state_listener: Optional[Callable] = None
        self._entity_states: Dict[str, "State"] = {}
        self._hass: "HomeAssistant" = hass
        self.entity_id: str = entity_id
        self.instance_id = uuid4().hex

    @callback
    def async_trigger_scene(self) -> None:
        """Trigger the schedule's scene."""
        self._hass.async_create_task(
            self._hass.services.async_call(
                "scene",
                "turn_on",
                service_data={"entity_id": self.entity_id},
                context=self._activation_context,
            )
        )

        @callback
        def save_state(entity_id: str, old_state: "State", new_state: "State") -> None:
            """Save prior states of an entity if it was triggered by this schedule."""
            if new_state.context == self._activation_context:
                self._entity_states[entity_id] = old_state

        self._async_state_listener = async_track_state_change(
            self._hass, MATCH_ALL, save_state
        )

        _LOGGER.info("Scheduler activated scene: %s", self.entity_id)

    @callback
    def async_undo_scene(self) -> None:
        """Restore the entities touched by the schedule."""
        if not self._entity_states:
            return

        for entity_id, state in self._entity_states.items():
            self._hass.states.async_set(
                entity_id,
                state.state,
                attributes=state.attributes,
                context=self._activation_context,
            )

        _LOGGER.info("Scheduler deactivated scene: %s", self.entity_id)


class Scheduler:
    """A class to manage scene schedules."""

    def __init__(self, hass: "HomeAssistant") -> None:
        """Initialize."""
        self._async_activation_listeners: Dict[str, Callable] = {}
        self._async_deactivation_listeners: Dict[str, str] = {}
        self._hass: "HomeAssistant" = hass
        self._latest_instances: List[ScheduleInstance] = []
        self.schedules: Dict[str, dict] = {}

    @callback
    def as_dict(self, schedule_id: str) -> dict:
        """Return a schedule in dict form."""
        schedule = self.schedules[schedule_id]
        return {
            CONF_SCHEDULE_ID: schedule_id,
            CONF_ENTITY_ID: schedule[CONF_ENTITY_ID],
            CONF_START_DATETIME: schedule[CONF_START_DATETIME].isoformat(),
            CONF_DURATION: schedule[CONF_DURATION],
            CONF_RRULE: str(schedule[CONF_RRULE]),
            CONF_ACTIVATION_CONTEXT_ID: schedule[CONF_ACTIVATION_CONTEXT].id,
        }

    @callback
    def async_create(
        self,
        entity_id: str,
        start_datetime: datetime,
        *,
        duration: Optional[int] = None,
        rrule_str: Optional[str] = None,
        activation_context_id: Optional[str] = None,
    ) -> dict:
        """Create a schedule.

        The rrule_str parameter must be an RFC5545-compliant string.
        The duration parameter is a number of seconds a schedule instance should last.
        """
        if start_datetime < datetime.now():
            raise ValueError("Dates in the past are not allowed")

        schedule_id = uuid4().hex
        schedule = {
            CONF_ENTITY_ID: entity_id,
            CONF_START_DATETIME: start_datetime,
            CONF_DURATION: duration,
            CONF_RRULE: rrulestr(rrule_str) if rrule_str else None,
            CONF_ACTIVATION_CONTEXT: Context(id=activation_context_id)
            if activation_context_id
            else Context(),
        }
        self.schedules[schedule_id] = schedule

        self.async_save()
        _LOGGER.info('Created schedule "%s": %s', schedule_id, schedule)

        self.async_schedule_next_instance(schedule_id)

        return self.as_dict(schedule_id)

    @callback
    def async_delete(
        self, schedule_id: str, *, remove_listeners: bool = True, save: bool = True
    ) -> dict:
        """Delete a schedule."""
        if schedule_id not in self.schedules:
            raise KeyError

        # This parameter is in place to handle two use cases:
        # 1. If the delete API is called, by default, we should assume there are
        #    listeners to cancel.
        # 2. If a completed schedule is deleted, the listeners won't exist.
        if remove_listeners:
            self.async_delete_latest_instance(schedule_id)

        return_payload = self.as_dict(schedule_id)
        self.schedules.pop(schedule_id)

        if save:
            self.async_save()
        _LOGGER.info('Deleted schedule "%s"', schedule_id)

        return return_payload

    async def async_delete_latest_instance(self, schedule_id: str) -> None:
        """Delete the latest (active) instance of a schedule."""
        if schedule_id in self._async_activation_listeners:
            cancel = self._async_activation_listeners.pop(schedule_id)
            cancel()
        if schedule_id in self._async_deactivation_listeners:
            cancel = self._async_deactivation_listeners.pop(schedule_id)
            cancel()

    async def async_load(self) -> None:
        """Load scheduler items."""

        def load() -> dict:
            """Load the items synchronously."""
            return load_json(self._hass.config.path(PERSISTENCE), default={})

        raw_schedules = await self._hass.async_add_job(load)
        for schedule in raw_schedules.values():
            self.async_create(
                schedule[CONF_ENTITY_ID],
                dt_util.parse_datetime(schedule[CONF_START_DATETIME]),
                duration=schedule[CONF_DURATION],
                rrule_str=schedule[CONF_RRULE],
                activation_context_id=schedule[CONF_ACTIVATION_CONTEXT_ID],
            )

    @callback
    def async_save(self) -> None:
        """Save the schedules to local storage."""

        def save() -> None:
            """Save."""
            save_json(
                self._hass.config.path(PERSISTENCE),
                {
                    schedule_id: self.as_dict(schedule_id)
                    for schedule_id, schedule in self.schedules.items()
                },
            )

        self._hass.async_add_job(save)
        self._hass.bus.async_fire(EVENT)

    @callback
    def async_schedule_next_instance(
        self, schedule_id: str, *, starting_from: datetime = None
    ) -> bool:
        """Schedule the next instance of a schedule."""
        schedule = self.schedules[schedule_id]

        if not schedule.get(CONF_RRULE):
            self.async_delete(schedule_id, remove_listeners=False)
            return

        if not starting_from:
            starting_from = datetime.now()
        start_dt = schedule[CONF_RRULE].after(starting_from, inc=True)

        if schedule.get(CONF_DURATION):
            end_dt = start_dt + timedelta(seconds=schedule[CONF_DURATION])
        else:
            end_dt = None

        instance = ScheduleInstance(
            self._hass, schedule[CONF_ENTITY_ID], schedule[CONF_ACTIVATION_CONTEXT]
        )

        @callback
        def schedule_start(call: datetime) -> None:
            """Trigger when the schedule starts."""
            instance.async_trigger_scene()
            if not end_dt:
                self.async_schedule_next_instance(schedule_id)

        @callback
        def schedule_end(call: datetime) -> None:
            """Trigger when the schedule ends."""
            instance.async_undo_scene()
            self.async_schedule_next_instance(schedule_id)

        self._async_activation_listeners[schedule_id] = async_track_point_in_time(
            self._hass, schedule_start, start_dt
        )
        if end_dt:
            self._async_deactivation_listeners[schedule_id] = async_track_point_in_time(
                self._hass, schedule_end, end_dt
            )

        _LOGGER.info(
            'Scheduled instance of schedule "%s" (start: %s / end: %s)',
            schedule_id,
            start_dt,
            end_dt,
        )

    def async_update(self, schedule_id: str, new_data: dict) -> dict:
        """Update a schedule."""
        if schedule_id not in self.schedules:
            raise KeyError

        new_data = SCHEDULE_UPDATE_SCHEMA(new_data)
        data = self.async_delete(schedule_id, save=False)
        data.update(new_data)
        return self.async_create(
            data[CONF_ENTITY_ID],
            data[CONF_RRULE],
            duration=data[CONF_DURATION],
            activation_context_id=data[CONF_ACTIVATION_CONTEXT].id,
        )


@callback
def websocket_handle_create(hass, connection, msg):
    """Handle creating a schedule."""
    try:
        schedule = hass.data[DOMAIN].async_create(
            msg[CONF_ENTITY_ID],
            msg[CONF_START_DATETIME],
            duration=msg.get(CONF_DURATION),
            rrule_str=msg.get(CONF_RRULE),
        )
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg[CONF_ID], "invalid_data", str(err))
        )
    else:
        connection.send_message(websocket_api.result_message(msg[CONF_ID], schedule))


@callback
def websocket_handle_delete(hass, connection, msg):
    """Handle deleting a schedule."""
    try:
        schedule = hass.data[DOMAIN].async_delete(msg[CONF_SCHEDULE_ID])
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
def websocket_handle_schedules(hass, connection, msg):
    """Handle getting all schedule."""
    connection.send_message(
        websocket_api.result_message(msg[CONF_ID], hass.data[DOMAIN].schedules)
    )


@callback
def websocket_handle_update(hass, connection, msg):
    """Handle updating a schedule."""
    msg_id = msg.pop("id")
    msg.pop("type")
    schedule_id = msg.pop("schedule_id")
    data = msg

    try:
        schedule = hass.data[DOMAIN].async_update(schedule_id, data)
        connection.send_message(
            websocket_api.error_message(
                msg[CONF_ID],
                "schedule_not_found",
                f"Cannot delete unknown schedule ID: {msg[CONF_SCHEDULE_ID]}",
            )
        )
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg_id, "invalid_data", str(err))
        )
    else:
        connection.send_message(websocket_api.result_message(msg_id, schedule))
