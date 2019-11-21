"""Support for scheduling scenes."""
import logging
from uuid import uuid4

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ENTITY_ID, CONF_ID
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json

DOMAIN = "scheduler"
_LOGGER = logging.getLogger(__name__)

PERSISTENCE = ".scheduler.json"

EVENT = "scheduler_updated"

CONF_ACTIVE = "active"
CONF_END_DATETIME = "end_datetime"
CONF_ITEM_ID = "item_id"
CONF_START_DATETIME = "start_datetime"

ITEM_UPDATE_SCHEMA = vol.Schema(
    {
        CONF_ENTITY_ID: cv.entity_id,
        CONF_START_DATETIME: str,
        CONF_END_DATETIME: str,
        CONF_ACTIVE: bool,
    }
)

WS_TYPE_SCHEDULER_ITEMS = "scheduler/items"
WS_TYPE_SCHEDULER_CREATE_ITEM = "scheduler/items/create"
WS_TYPE_SCHEDULER_UPDATE_ITEM = "scheduler/items/update"
WS_TYPE_SCHEDULER_DELETE_ITEM = "scheduler/items/delete"
WS_TYPE_SCHEDULER_CLEAR_INACTIVE_ITEMS = "scheduler/items/clear"

SCHEMA_WEBSOCKET_CLEAR_INACTIVE_ITEMS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_SCHEDULER_CLEAR_INACTIVE_ITEMS}
)

SCHEMA_WEBSOCKET_CREATE_ITEM = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_CREATE_ITEM,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_START_DATETIME): str,
        vol.Required(CONF_END_DATETIME): str,
    }
)

SCHEMA_WEBSOCKET_DELETE_ITEM = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_DELETE_ITEM,
        vol.Required(CONF_ITEM_ID): str,
    }
)

SCHEMA_WEBSOCKET_ITEMS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_SCHEDULER_ITEMS}
)

SCHEMA_WEBSOCKET_UPDATE_ITEM = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SCHEDULER_UPDATE_ITEM,
        vol.Required(CONF_ITEM_ID): str,
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
        WS_TYPE_SCHEDULER_CLEAR_INACTIVE_ITEMS,
        websocket_handle_clear,
        SCHEMA_WEBSOCKET_CLEAR_INACTIVE_ITEMS,
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_CREATE_ITEM,
        websocket_handle_create,
        SCHEMA_WEBSOCKET_CREATE_ITEM,
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_DELETE_ITEM,
        websocket_handle_delete,
        SCHEMA_WEBSOCKET_DELETE_ITEM,
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_ITEMS, websocket_handle_items, SCHEMA_WEBSOCKET_ITEMS
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULER_UPDATE_ITEM,
        websocket_handle_update,
        SCHEMA_WEBSOCKET_UPDATE_ITEM,
    )

    return True


class Scheduler:
    """A class to handle scene schedules."""

    def __init__(self, hass):
        """Initialize."""
        self._hass = hass
        self.items = {}

    @callback
    def async_create(self, entity_id, start_datetime, end_datetime=None):
        """Add a scheduler item."""
        item_id = uuid4().hex
        item = {
            CONF_ID: item_id,
            CONF_ENTITY_ID: entity_id,
            CONF_START_DATETIME: start_datetime,
            CONF_END_DATETIME: end_datetime,
            CONF_ACTIVE: True,
        }
        self.items[item_id] = item
        self._hass.async_add_job(self.save)
        return item

    @callback
    def async_delete(self, item_id):
        """Delete a scheduler item."""
        if item_id not in self.items:
            raise KeyError

        item = self.items.pop(item_id)
        self._hass.async_add_job(self.save)
        return item

    @callback
    def async_update(self, item_id, data):
        """Update a scheduler item."""
        if item_id not in self.items:
            raise KeyError

        item = self.items[item_id]
        data = ITEM_UPDATE_SCHEMA(data)
        item.update(data)
        self._hass.async_add_job(self.save)
        return item

    @callback
    def async_clear_inactive(self):
        """Clear inactive scheduler items."""
        self.items = {
            item_id: item for item_id, item in self.items.items() if item[CONF_ACTIVE]
        }
        self._hass.async_add_job(self.save)

    async def async_load(self):
        """Load scheduler items."""

        def load():
            """Load the items synchronously."""
            return load_json(self._hass.config.path(PERSISTENCE), default={})

        self.items = await self._hass.async_add_job(load)

    def save(self):
        """Save the items."""
        save_json(self._hass.config.path(PERSISTENCE), self.items)


@callback
def websocket_handle_create(hass, connection, msg):
    """Handle creating a scheduler item."""
    item = hass.data[DOMAIN].async_create(
        msg[CONF_ENTITY_ID], msg[CONF_START_DATETIME], msg[CONF_END_DATETIME]
    )
    hass.bus.async_fire(EVENT)
    connection.send_message(websocket_api.result_message(msg[CONF_ID], item))


@callback
def websocket_handle_clear(hass, connection, msg):
    """Handle clearing inactive items from the scheduler."""
    hass.data[DOMAIN].async_clear_inactive()
    hass.bus.async_fire(EVENT)
    connection.send_message(websocket_api.result_message(msg[CONF_ID]))


@callback
def websocket_handle_delete(hass, connection, msg):
    """Handle deleting a scheduler item."""
    try:
        item = hass.data[DOMAIN].async_delete(msg[CONF_ITEM_ID])
        hass.bus.async_fire(EVENT)
        connection.send_message(websocket_api.result_message(msg[CONF_ID], item))
    except KeyError:
        connection.send_message(
            websocket_api.error_message(
                msg[CONF_ID], "item_not_found", "Item not found"
            )
        )


@callback
def websocket_handle_items(hass, connection, msg):
    """Handle getting all scheduler items."""
    connection.send_message(
        websocket_api.result_message(msg[CONF_ID], hass.data[DOMAIN].items)
    )


@callback
def websocket_handle_update(hass, connection, msg):
    """Handle updating a scheduler item."""
    msg_id = msg.pop("id")
    item_id = msg.pop("item_id")
    msg.pop("type")
    data = msg

    try:
        item = hass.data[DOMAIN].async_update(item_id, data)
        hass.bus.async_fire(EVENT)
        connection.send_message(websocket_api.result_message(msg_id, item))
    except KeyError:
        connection.send_message(
            websocket_api.error_message(msg_id, "item_not_found", "Item not found")
        )
