"""Support for scheduling scenes."""
from datetime import datetime
import logging
from uuid import uuid4

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

DOMAIN = "scheduler"
_LOGGER = logging.getLogger(__name__)

PERSISTENCE = ".scheduler.json"

EVENT = "scheduler_updated"

CONF_ACTIVATION_CONTEXT_ID = "activation_context_id"
CONF_END_DATETIME = "end_datetime"
CONF_SCHEDULE_ID = "schedule_id"
CONF_START_DATETIME = "start_datetime"

ITEM_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCHEDULE_ID): str,
        vol.Optional(CONF_ACTIVATION_CONTEXT_ID): str,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_START_DATETIME): str,
        vol.Optional(CONF_END_DATETIME): vol.Any(str, None),
    }
)

ITEM_UPDATE_SCHEMA = vol.Schema(
    {CONF_ENTITY_ID: cv.entity_id, CONF_START_DATETIME: str, CONF_END_DATETIME: str}
)

WS_TYPE_SCHEDULER_CLEAR_EXPIRED = "scheduler/items/clear_expired"
WS_TYPE_SCHEDULER_CREATE_SCHEDULE = "scheduler/items/create"
WS_TYPE_SCHEDULER_DELETE_SCHEDULE = "scheduler/items/delete"
WS_TYPE_SCHEDULER_ITEMS = "scheduler/items"
WS_TYPE_SCHEDULER_UPDATE_SCHEDULE = "scheduler/items/update"

SCHEMA_WEBSOCKET_CLEAR_EXPIRED = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_SCHEDULER_CLEAR_EXPIRED}
)

SCHEMA_WEBSOCKET_CREATE_SCHEDULE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_CREATE_SCHEDULE,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_START_DATETIME): str,
        vol.Optional(CONF_END_DATETIME): str,
    }
)

SCHEMA_WEBSOCKET_DELETE_SCHEDULE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_DELETE_SCHEDULE,
        vol.Required(CONF_SCHEDULE_ID): str,
    }
)

SCHEMA_WEBSOCKET_SCHEDULES = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_SCHEDULER_ITEMS}
)

SCHEMA_WEBSOCKET_UPDATE_SCHEDULE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_UPDATE_SCHEDULE,
        vol.Required(CONF_SCHEDULE_ID): str,
        vol.Optional(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_START_DATETIME): str,
        vol.Optional(CONF_END_DATETIME): str,
    }
)


async def async_setup(hass, config):
    """Set up the scheduler."""
    if DOMAIN not in config:
        return True

    scheduler = hass.data[DOMAIN] = Scheduler(hass)
    await scheduler.async_load()

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_CLEAR_EXPIRED,
        websocket_handle_clear_expired,
        SCHEMA_WEBSOCKET_CLEAR_EXPIRED,
    )
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
        WS_TYPE_SCHEDULER_ITEMS, websocket_handle_items, SCHEMA_WEBSOCKET_SCHEDULES
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_UPDATE_SCHEDULE,
        websocket_handle_update,
        SCHEMA_WEBSOCKET_UPDATE_SCHEDULE,
    )

    return True


class Schedule:
    """A class that defines a scene schedule."""

    def __init__(
        self,
        hass,
        entity_id,
        start_datetime,
        end_datetime=None,
        schedule_id=None,
        activation_context_id=None,
    ):
        """Initialize."""
        now = datetime.now()
        if (start_datetime and start_datetime < now) or (
            end_datetime and end_datetime < now
        ):
            raise ValueError("Dates in the past are not allowed")

        self._async_state_listener = None
        self._entity_states = {}
        self._hass = hass
        self.end_datetime = end_datetime
        self.entity_id = entity_id
        self.start_datetime = start_datetime

        if schedule_id:
            self.schedule_id = schedule_id
        else:
            self.schedule_id = uuid4().hex

        if activation_context_id:
            self._activation_context = Context(id=activation_context_id)
        else:
            self._activation_context = Context()

    @classmethod
    def from_dict(cls, hass, conf):
        """Instantiate a schedule from a dict of parameters."""
        try:
            ITEM_SCHEMA(conf)
        except vol.Invalid as err:
            raise ValueError(f"Cannot create schedule from invalid data: {err}")

        start_datetime = dt_util.parse_datetime(conf[CONF_START_DATETIME])
        if conf.get(CONF_END_DATETIME):
            end_datetime = dt_util.parse_datetime(conf[CONF_END_DATETIME])
        else:
            end_datetime = None
        return cls(
            hass,
            conf[CONF_ENTITY_ID],
            start_datetime,
            end_datetime=end_datetime,
            schedule_id=conf.get(CONF_SCHEDULE_ID),
            activation_context_id=conf.get(CONF_ACTIVATION_CONTEXT_ID),
        )

    def as_dict(self):
        """Output the schedule as a dict."""
        return {
            CONF_SCHEDULE_ID: self.schedule_id,
            CONF_ACTIVATION_CONTEXT_ID: self._activation_context.id,
            CONF_ENTITY_ID: self.entity_id,
            CONF_START_DATETIME: self.start_datetime.isoformat(),
            CONF_END_DATETIME: self.end_datetime.isoformat()
            if self.end_datetime
            else None,
        }

    @callback
    def async_activate(self):
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
        def save_state(entity_id, old_state, new_state):
            """Save prior states of an entity if it was triggered by this schedule."""
            if new_state.context != self._activation_context:
                return
            self._entity_states[entity_id] = old_state

        self._async_state_listener = async_track_state_change(
            self._hass, MATCH_ALL, save_state
        )

        _LOGGER.info("Scheduler activated scene: %s", self.entity_id)

    @callback
    def async_deactivate(self):
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
    """A class that manages scene schedules."""

    def __init__(self, hass):
        """Initialize."""
        self._async_activation_listeners = {}
        self._async_deactivation_listeners = {}
        self._hass = hass
        self.schedules = {}

    @callback
    def async_clear_expired(self):
        """Clear schedules that are in the past."""
        now = datetime.now()

        for schedule_id, schedule in self.schedules.items():
            if schedule[CONF_START_DATETIME] < now and (
                schedule.get(CONF_END_DATETIME) and schedule[CONF_END_DATETIME] < now
            ):
                self.async_delete(schedule_id)

        self.async_save()

    @callback
    def async_create(
        self,
        entity_id,
        start_datetime,
        end_datetime=None,
        schedule_id=None,
        activation_context=None,
    ):
        """Add a scheduler item."""
        schedule = Schedule(
            self._hass,
            entity_id,
            dt_util.parse_datetime(start_datetime),
            dt_util.parse_datetime(end_datetime) if end_datetime else None,
            schedule_id,
            activation_context,
        )

        @callback
        def schedule_start(call):
            """Trigger when the schedule starts."""
            schedule.async_activate()
            if not schedule.end_datetime:
                self._async_activation_listeners.pop(schedule.schedule_id)
                self.schedules.pop(schedule.schedule_id)
                self.async_save()

        @callback
        def schedule_end(call):
            """Trigger when the schedule ends."""
            schedule.async_deactivate()
            self._async_deactivation_listeners.pop(schedule.schedule_id)
            self.schedules.pop(schedule.schedule_id)
            self.async_save()

        self._async_activation_listeners[
            schedule.schedule_id
        ] = async_track_point_in_time(
            self._hass, schedule_start, schedule.start_datetime
        )
        if schedule.end_datetime:
            self._async_deactivation_listeners[
                schedule.schedule_id
            ] = async_track_point_in_time(
                self._hass, schedule_end, schedule.end_datetime
            )

        self.schedules[schedule.schedule_id] = schedule
        self.async_save()
        return schedule.as_dict()

    @callback
    def async_delete(self, schedule_id, *, save=True):
        """Delete a schedule."""
        if schedule_id not in self.schedules:
            raise KeyError

        schedule = self.schedules.pop(schedule_id)

        if schedule_id in self._async_activation_listeners:
            cancel = self._async_activation_listeners.pop(schedule_id)
            cancel()
        if schedule_id in self._async_deactivation_listeners:
            cancel = self._async_deactivation_listeners.pop(schedule_id)
            cancel()

        if save:
            self.async_save()
        return schedule.as_dict()

    async def async_load(self):
        """Load scheduler items."""

        def load():
            """Load the items synchronously."""
            return load_json(self._hass.config.path(PERSISTENCE), default={})

        raw_schedules = await self._hass.async_add_job(load)
        for schedule in raw_schedules.values():
            self.async_create(
                schedule[CONF_ENTITY_ID],
                schedule[CONF_START_DATETIME],
                schedule[CONF_END_DATETIME],
                schedule[CONF_SCHEDULE_ID],
                schedule[CONF_ACTIVATION_CONTEXT_ID],
            )

    @callback
    def async_save(self):
        """Save the items."""

        def save():
            """Save the items synchronously."""
            save_json(
                self._hass.config.path(PERSISTENCE),
                {
                    schedule_id: schedule.as_dict()
                    for schedule_id, schedule in self.schedules.items()
                },
            )

        self._hass.async_add_job(save)
        self._hass.bus.async_fire(EVENT)

    @callback
    def async_update(self, schedule_id, new_data):
        """Update a schedule."""
        if schedule_id not in self.schedules:
            raise KeyError

        try:
            data = ITEM_UPDATE_SCHEMA(new_data)
        except vol.Invalid as err:
            raise ValueError(f"Cannot update schedule with invalid data: {err}")

        data = self.async_delete(schedule_id, save=False)
        data.update(new_data)
        return self.async_create(
            data[CONF_ENTITY_ID],
            data[CONF_START_DATETIME],
            data[CONF_END_DATETIME],
            data[CONF_SCHEDULE_ID],
            data[CONF_ACTIVATION_CONTEXT_ID],
        )


@callback
def websocket_handle_clear_expired(hass, connection, msg):
    """Handle creating a schedule."""
    hass.data[DOMAIN].async_clear_expired()
    connection.send_message(
        websocket_api.result_message(msg[CONF_ID], hass.data[DOMAIN].schedules)
    )


@callback
def websocket_handle_create(hass, connection, msg):
    """Handle creating a schedule."""
    try:
        schedule = hass.data[DOMAIN].async_create(
            msg[CONF_ENTITY_ID], msg[CONF_START_DATETIME], msg.get(CONF_END_DATETIME)
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
    except KeyError as err:
        connection.send_message(
            websocket_api.error_message(msg[CONF_ID], "schedule_not_found", str(err))
        )
    else:
        connection.send_message(websocket_api.result_message(msg[CONF_ID], schedule))


@callback
def websocket_handle_items(hass, connection, msg):
    """Handle getting all schedule."""
    connection.send_message(
        websocket_api.result_message(msg[CONF_ID], hass.data[DOMAIN].schedules)
    )


@callback
def websocket_handle_update(hass, connection, msg):
    """Handle updating a schedule."""
    msg_id = msg.pop("id")
    schedule_id = msg.pop("schedule_id")
    msg.pop("type")
    data = msg

    try:
        schedule = hass.data[DOMAIN].async_update(schedule_id, data)
    except KeyError as err:
        connection.send_message(
            websocket_api.error_message(msg[CONF_ID], "schedule_not_found", str(err))
        )
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg_id, "invalid_data", str(err))
        )
    else:
        connection.send_message(websocket_api.result_message(msg_id, schedule))
