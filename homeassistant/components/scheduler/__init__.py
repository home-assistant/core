"""Support for scheduling scenes."""
from datetime import datetime
import logging
from uuid import uuid4

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ENTITY_ID, CONF_ID
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.util.json import load_json, save_json

DOMAIN = "scheduler"
_LOGGER = logging.getLogger(__name__)

PERSISTENCE = ".scheduler.json"

EVENT = "scheduler_updated"

CONF_END_DATETIME = "end_datetime"
CONF_SCHEDULE_ID = "schedule_id"
CONF_START_DATETIME = "start_datetime"
CONF_ENABLED = "enabled"

ITEM_UPDATE_SCHEMA = vol.Schema(
    {
        CONF_ENTITY_ID: cv.entity_id,
        CONF_START_DATETIME: str,
        CONF_END_DATETIME: str,
        CONF_ENABLED: bool,
    }
)

WS_TYPE_SCHEDULER_CLEAR_INACTIVE_SCHEDULES = "scheduler/items/clear"
WS_TYPE_SCHEDULER_CREATE_SCHEDULE = "scheduler/items/create"
WS_TYPE_SCHEDULER_DELETE_SCHEDULE = "scheduler/items/delete"
WS_TYPE_SCHEDULER_DISABLE_SCHEDULE = "scheduler/items/disable"
WS_TYPE_SCHEDULER_ENABLE_SCHEDULE = "scheduler/items/enable"
WS_TYPE_SCHEDULER_SCHEDULES = "scheduler/items"
WS_TYPE_SCHEDULER_UPDATE_SCHEDULE = "scheduler/items/update"

SCHEMA_WEBSOCKET_CLEAR_INACTIVE_SCHEDULES = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_SCHEDULER_CLEAR_INACTIVE_SCHEDULES}
)

SCHEMA_WEBSOCKET_CREATE_SCHEDULE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_CREATE_SCHEDULE,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_START_DATETIME): str,
        vol.Required(CONF_END_DATETIME): str,
    }
)

SCHEMA_WEBSOCKET_DELETE_SCHEDULE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_DELETE_SCHEDULE,
        vol.Required(CONF_SCHEDULE_ID): str,
    }
)

SCHEMA_WEBSOCKET_DISABLE_SCHEDULE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_DISABLE_SCHEDULE,
        vol.Required(CONF_SCHEDULE_ID): str,
    }
)

SCHEMA_WEBSOCKET_ENABLE_SCHEDULE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_ENABLE_SCHEDULE,
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


def raise_on_invalid_dates(start_datetime, end_datetime):
    """Raise an error if either the start or end datetimes are invalid."""
    now = datetime.now()

    # Since it's possible to pass None for both parameters, check that case and return
    # quickly if needed:
    if not start_datetime and not end_datetime:
        return

    if start_datetime:
        start_dt = dt_util.parse_datetime(start_datetime)

    if end_datetime:
        end_dt = dt_util.parse_datetime(end_datetime)

    if (start_datetime and start_dt < now) or (end_datetime and end_dt < now):
        raise ValueError


async def async_setup(hass, config):
    """Set up the scheduler."""
    if DOMAIN not in config:
        return True

    scheduler = hass.data[DOMAIN] = Scheduler(hass)
    await scheduler.async_load()

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_CLEAR_INACTIVE_SCHEDULES,
        websocket_handle_clear,
        SCHEMA_WEBSOCKET_CLEAR_INACTIVE_SCHEDULES,
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
        WS_TYPE_SCHEDULER_DISABLE_SCHEDULE,
        websocket_handle_disable,
        SCHEMA_WEBSOCKET_DISABLE_SCHEDULE,
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_ENABLE_SCHEDULE,
        websocket_handle_enable,
        SCHEMA_WEBSOCKET_ENABLE_SCHEDULE,
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


class Scheduler:
    """A class to handle scene schedules."""

    def __init__(self, hass):
        """Initialize."""
        self._hass = hass
        self.items = {}

    @callback
    def _async_set_enabled(self, schedule_id, enabled):
        """Enable/disable a schedule."""
        if schedule_id not in self.items:
            raise KeyError

        item = self.items[schedule_id]
        item[CONF_ENABLED] = enabled
        self.async_save()
        return item

    @callback
    def async_clear_disabled(self):
        """Clear disabled/inactive scheduler items."""
        self.items = {
            schedule_id: item
            for schedule_id, item in self.items.items()
            if item[CONF_ENABLED]
        }
        self.async_save()

    @callback
    def async_create(self, entity_id, start_datetime, end_datetime=None):
        """Add a scheduler item."""
        raise_on_invalid_dates(start_datetime, end_datetime)

        schedule_id = uuid4().hex
        item = {
            CONF_ID: schedule_id,
            CONF_ENTITY_ID: entity_id,
            CONF_START_DATETIME: start_datetime,
            CONF_END_DATETIME: end_datetime,
            CONF_ENABLED: True,
        }
        self.items[schedule_id] = item
        self.async_save()
        return item

    @callback
    def async_delete(self, schedule_id):
        """Delete a scheduler item."""
        if schedule_id not in self.items:
            raise KeyError

        item = self.items.pop(schedule_id)
        self.async_save()
        return item

    @callback
    def async_disable(self, schedule_id):
        """Disable a scheduler item."""
        return self._async_set_enabled(schedule_id, False)

    @callback
    def async_enable(self, schedule_id):
        """Enable a scheduler item."""
        return self._async_set_enabled(schedule_id, True)

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

        item = self.items[schedule_id]
        data = ITEM_UPDATE_SCHEMA(data)
        item.update(data)
        self.async_save()
        return item


@callback
def websocket_handle_create(hass, connection, msg):
    """Handle creating a schedule."""
    try:
        item = hass.data[DOMAIN].async_create(
            msg[CONF_ENTITY_ID], msg[CONF_START_DATETIME], msg[CONF_END_DATETIME]
        )
    except ValueError:
        connection.send_message(
            websocket_api.error_message(
                msg[CONF_ID], "date_in_past", "Can't have a date in the past"
            )
        )
    else:
        connection.send_message(websocket_api.result_message(msg[CONF_ID], item))


@callback
def websocket_handle_clear(hass, connection, msg):
    """Handle clearing disabled schedules from the scheduler."""
    hass.data[DOMAIN].async_clear_inactive()
    connection.send_message(websocket_api.result_message(msg[CONF_ID]))


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
def websocket_handle_disable(hass, connection, msg):
    """Handle disabling a schedule."""
    try:
        item = hass.data[DOMAIN].async_disable(msg[CONF_SCHEDULE_ID])
    except KeyError:
        connection.send_message(
            websocket_api.error_message(
                msg[CONF_ID], "schedule_not_found", "Schedule not found"
            )
        )
    else:
        connection.send_message(websocket_api.result_message(msg[CONF_ID], item))


@callback
def websocket_handle_enable(hass, connection, msg):
    """Handle enabling a schedule."""
    try:
        item = hass.data[DOMAIN].async_enable(msg[CONF_SCHEDULE_ID])
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
    except ValueError:
        connection.send_message(
            websocket_api.error_message(
                msg_id, "date_in_past", "Can't have a date in the past"
            )
        )
    else:
        connection.send_message(websocket_api.result_message(msg_id, item))
