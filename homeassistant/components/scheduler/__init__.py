"""Support for scheduling scenes."""
from datetime import datetime
import logging
from uuid import uuid4

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ENTITY_ID, CONF_ID
from homeassistant.core import Context, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_time
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

ITEM_UPDATE_SCHEMA = vol.Schema(
    {CONF_ENTITY_ID: cv.entity_id, CONF_START_DATETIME: str, CONF_END_DATETIME: str}
)

WS_TYPE_SCHEDULER_CREATE_SCHEDULE = "scheduler/items/create"
WS_TYPE_SCHEDULER_DELETE_SCHEDULE = "scheduler/items/delete"
WS_TYPE_SCHEDULER_SCHEDULES = "scheduler/items"
WS_TYPE_SCHEDULER_UPDATE_SCHEDULE = "scheduler/items/update"

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
    {vol.Required("type"): WS_TYPE_SCHEDULER_SCHEDULES}
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
        WS_TYPE_SCHEDULER_SCHEDULES, websocket_handle_items, SCHEMA_WEBSOCKET_SCHEDULES
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_UPDATE_SCHEDULE,
        websocket_handle_update,
        SCHEMA_WEBSOCKET_UPDATE_SCHEDULE,
    )

    return True


def raise_on_invalid_dates(start_datetime, end_datetime):
    """Raise an error if either the start or end datetimes are invalid."""
    now = datetime.now()
    if (start_datetime and start_datetime < now) or (
        end_datetime and end_datetime < now
    ):
        raise ValueError("Dates in the past are not allowed")


class Scheduler:
    """A class to handle scene schedules."""

    def __init__(self, hass):
        """Initialize."""
        self._hass = hass
        self._async_activation_listeners = {}
        self._async_deactivation_listeners = {}
        self.items = {}

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
        start = dt_util.parse_datetime(start_datetime)
        try:
            end = dt_util.parse_datetime(end_datetime)
        except TypeError:
            end = None

        raise_on_invalid_dates(start, end)

        if not schedule_id:
            schedule_id = uuid4().hex
        if not activation_context:
            activation_context = Context()

        item = {
            CONF_ID: schedule_id,
            CONF_ENTITY_ID: entity_id,
            CONF_START_DATETIME: start_datetime,
            CONF_END_DATETIME: end_datetime,
            CONF_ACTIVATION_CONTEXT_ID: activation_context.id,
        }

        @callback
        def activate(call):
            """Activate the scene."""
            self._hass.async_create_task(
                self._hass.services.async_call(
                    "scene",
                    "turn_on",
                    service_data={"entity_id": entity_id},
                    context=activation_context,
                )
            )

            _LOGGER.info("Scheduler activated scene: %s", entity_id)

            self._async_activation_listeners.pop(schedule_id)
            self.items.pop(schedule_id)
            self.async_save()

        self.items[schedule_id] = item
        self.async_save()

        self._async_activation_listeners[schedule_id] = async_track_point_in_time(
            self._hass, activate, start
        )

        return item

    @callback
    def async_delete(self, schedule_id):
        """Delete a scheduler item."""
        if schedule_id not in self.items:
            raise KeyError

        for listener_repo in (
            self._async_activation_listeners,
            self._async_deactivation_listeners,
        ):
            if schedule_id in listener_repo:
                cancel = listener_repo(schedule_id)
                cancel()

        item = self.items.pop(schedule_id)
        self.async_save()
        return item

    async def async_load(self):
        """Load scheduler items."""

        def load():
            """Load the items synchronously."""
            return load_json(self._hass.config.path(PERSISTENCE), default={})

        self.items = await self._hass.async_add_job(load)

    @callback
    def async_save(self):
        """Save the items."""

        def save():
            """Save the items synchronously."""
            save_json(self._hass.config.path(PERSISTENCE), self.items)

        self._hass.async_add_job(save)
        self._hass.bus.async_fire(EVENT)

    @callback
    def async_update(self, schedule_id, data):
        """Update a scheduler item."""
        if schedule_id not in self.items:
            raise KeyError

        raise_on_invalid_dates(
            data.get(CONF_START_DATETIME), data.get(CONF_END_DATETIME)
        )

        data = ITEM_UPDATE_SCHEMA(data)
        item = self.async_delete(schedule_id)
        item.update(data)

        return self.async_create(
            item[CONF_ENTITY_ID],
            item[CONF_START_DATETIME],
            end_datetime=item[CONF_END_DATETIME],
            schedule_id=item[CONF_SCHEDULE_ID],
            activation_context=item[CONF_ACTIVATION_CONTEXT_ID],
        )


@callback
def websocket_handle_create(hass, connection, msg):
    """Handle creating a schedule."""
    try:
        item = hass.data[DOMAIN].async_create(
            msg[CONF_ENTITY_ID], msg[CONF_START_DATETIME], msg.get(CONF_END_DATETIME)
        )
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg[CONF_ID], "invalid_parameter", str(err))
        )
    else:
        connection.send_message(websocket_api.result_message(msg[CONF_ID], item))


@callback
def websocket_handle_delete(hass, connection, msg):
    """Handle deleting a schedule."""
    try:
        item = hass.data[DOMAIN].async_delete(msg[CONF_SCHEDULE_ID])
    except KeyError:
        connection.send_message(
            websocket_api.error_message(
                msg[CONF_ID], "schedule_not_found", "Schedule not found"
            )
        )
    else:
        connection.send_message(websocket_api.result_message(msg[CONF_ID], item))


@callback
def websocket_handle_items(hass, connection, msg):
    """Handle getting all schedule."""
    connection.send_message(
        websocket_api.result_message(msg[CONF_ID], hass.data[DOMAIN].items)
    )


@callback
def websocket_handle_update(hass, connection, msg):
    """Handle updating a schedule."""
    msg_id = msg.pop("id")
    schedule_id = msg.pop("schedule_id")
    msg.pop("type")
    data = msg

    try:
        item = hass.data[DOMAIN].async_update(schedule_id, data)
    except KeyError:
        connection.send_message(
            websocket_api.error_message(
                msg_id, "schedule_not_found", "Schedule not found"
            )
        )
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg_id, "invalid_parameter", str(err))
        )
    else:
        connection.send_message(websocket_api.result_message(msg_id, item))
