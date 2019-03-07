"""
Support for todo lists.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/todolist/
"""
from datetime import timedelta
import logging
from functools import partial

import voluptuous as vol

from homeassistant.components import group
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.components import websocket_api
from homeassistant.const import (CONF_TYPE, ATTR_ENTITY_ID, ATTR_ID)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'todolist'
DEPENDENCIES = ['group']

SCAN_INTERVAL = timedelta(seconds=300)

ATTR_COMPLETE = 'complete'
ATTR_NAME = 'name'
ATTR_TASK = 'task'
ATTR_SHOW_COMPLETED = 'show_completed'

GROUP_NAME_ALL_TODO_LISTS = 'all todo lists'
ENTITY_ID_ALL_TODO_LISTS = group.ENTITY_ID_FORMAT.format('all_todo_lists')
DEFAULT_NAME = 'Todo list'
TODO_LISTS = 'todo_lists'

# platform schema

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({})
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE.extend(PLATFORM_SCHEMA.schema)

# WebSocket services' configuration

WS_TYPE_LIST_TASKS = 'todolist/tasks/list'
WS_TYPE_CREATE_TASK = 'todolist/tasks/create'
WS_TYPE_UPDATE_TASK = 'todolist/tasks/update'
WS_TYPE_CLEAR_COMPLETED = 'todolist/tasks/clear'

TODO_LIST_SERVICE_SCHEMA = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required(ATTR_ENTITY_ID): cv.string,
})

SCHEMA_WEBSOCKET_LIST_TASKS = TODO_LIST_SERVICE_SCHEMA.extend({
    vol.Required(CONF_TYPE): WS_TYPE_LIST_TASKS,
    vol.Optional(ATTR_SHOW_COMPLETED): cv.boolean,
})

SCHEMA_WEBSOCKET_CREATE_TASK = TODO_LIST_SERVICE_SCHEMA.extend({
    vol.Required(CONF_TYPE): WS_TYPE_CREATE_TASK,
    vol.Required(ATTR_TASK): vol.Schema({
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_COMPLETE): cv.boolean,
    }, extra=vol.ALLOW_EXTRA)
})

SCHEMA_WEBSOCKET_UPDATE_TASK = TODO_LIST_SERVICE_SCHEMA.extend({
    vol.Required(CONF_TYPE): WS_TYPE_UPDATE_TASK,
    vol.Required(ATTR_TASK): vol.Schema({
        vol.Required(ATTR_ID): cv.string,
        vol.Optional(ATTR_NAME): cv.string,
        vol.Optional(ATTR_COMPLETE): cv.boolean,
    }, extra=vol.ALLOW_EXTRA)
})

SCHEMA_WEBSOCKET_CLEAR_COMPLETED = TODO_LIST_SERVICE_SCHEMA.extend({
    vol.Required(CONF_TYPE): WS_TYPE_CLEAR_COMPLETED,
})

async def async_setup(hass, config):
    """Offer web services for todo lists."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_TODO_LISTS)
    await component.async_setup(config)

    hass.data[DOMAIN] = component

    hass.components.websocket_api.async_register_command(
        WS_TYPE_LIST_TASKS,
        websocket_list_tasks,
        SCHEMA_WEBSOCKET_LIST_TASKS)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_CREATE_TASK,
        websocket_create_task,
        SCHEMA_WEBSOCKET_CREATE_TASK)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_UPDATE_TASK,
        websocket_update_task,
        SCHEMA_WEBSOCKET_UPDATE_TASK)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_CLEAR_COMPLETED,
        websocket_clear_completed,
        SCHEMA_WEBSOCKET_CLEAR_COMPLETED)

    return True

def get_todolist_instance(hass, connection, entity_id):
    component = hass.data[DOMAIN]
    todolist = component.get_entity(entity_id)

    if todolist is None:
        connection.send_message(websocket_api.error_message(
            msg.get(ATTR_ID), 'entity_not_found', 'Entity not found'))
        return

    return todolist

@websocket_api.async_response
async def websocket_list_tasks(hass, connection, msg):
    """Dispatch list tasks service call to entity.

    Async friendly.
    """
    todolist = get_todolist_instance(hass, connection, msg.get(ATTR_ENTITY_ID))

    show_completed = msg.get(ATTR_SHOW_COMPLETED)
    platform_items = await todolist.async_list_tasks(show_completed)

    if platform_items is None:
        connection.send_message(websocket_api.error_message(
            msg.get(ATTR_ID), 'list_tasks_failed',
            'Failed to list tasks'))
        return

    todo_items = list(map(todolist.map_to_todo_item, platform_items))

    connection.send_message(websocket_api.result_message(
        msg.get(ATTR_ID), todo_items))


@websocket_api.async_response
async def websocket_create_task(hass, connection, msg):
    """Dispatch add task service call to entity.

    Async friendly.
    """
    todolist = get_todolist_instance(hass, connection, msg.get(ATTR_ENTITY_ID))

    new_todo_item = msg.get(ATTR_TASK)
    new_platform_item = todolist.map_from_todo_item(new_todo_item)
    created_platform_item = await todolist.async_create_task(new_platform_item)

    if created_platform_item is None:
        connection.send_message(websocket_api.error_message(
            msg.get(ATTR_ID), 'create_task_failed',
            'Failed to create new task'))
        return

    todo_created_item = todolist.map_to_todo_item(created_platform_item)

    connection.send_message(websocket_api.result_message(
        msg.get(ATTR_ID), todo_created_item))

@websocket_api.async_response
async def websocket_update_task(hass, connection, msg):
    """Dispatch update task service call to entity.

    Async friendly.
    """
    todolist = get_todolist_instance(hass, connection, msg.get(ATTR_ENTITY_ID))

    new_todo_item = msg.get(ATTR_TASK)
    new_platform_item = todolist.map_from_todo_item(new_todo_item)
    updated_platform_item = await todolist.async_update_task(new_platform_item)

    if updated_platform_item is None:
        connection.send_message(websocket_api.error_message(
            msg.get(ATTR_ID), 'update_task_failed',
            'Failed to update task'))
        return

    updated_todo_item = todolist.map_to_todo_item(updated_platform_item)

    connection.send_message(websocket_api.result_message(
        msg.get(ATTR_ID), updated_todo_item))

@websocket_api.async_response
async def websocket_clear_completed(hass, connection, msg):
    """Dispatch clear completed tasks service call to entity.

    Async friendly.
    """
    todolist = get_todolist_instance(hass, connection, msg.get(ATTR_ENTITY_ID))

    await todolist.async_clear_completed()

    connection.send_message(websocket_api.result_message(
        msg.get(ATTR_ID), True))

class TodoListBase(Entity):
    """Representation of a todo list."""

    def map_from_todo_item(self, todo_item):
        """Converts todo item -> platform todo item."""
        raise NotImplementedError()

    def map_to_todo_item(self, platform_item):
        """Converts platform todo item -> todo item."""
        raise NotImplementedError()

    def list_tasks(self, show_completed=True):
        """List tasks."""
        raise NotImplementedError()

    def async_list_tasks(self, show_completed=True):
        """List tasks.

        This method must be run in the event loop and returns a coroutine.
        """
        fn_list_tasks = partial(self.list_tasks, show_completed)
        return self.hass.async_add_job(fn_list_tasks)

    def create_task(self, new_task):
        """Create a new task."""
        raise NotImplementedError()

    def async_create_task(self, new_task):
        """Create a new task.

        This method must be run in the event loop and returns a coroutine.
        """
        fn_create_task = partial(self.create_task, new_task)
        return self.hass.async_add_job(fn_create_task)

    def update_task(self, updated_task):
        """Update an existing task.

        The task's id is contained within the task object."""
        raise NotImplementedError()

    def async_update_task(self, updated_task):
        """Update an existing task.

        The task's id is contained within the task object.
        This method must be run in the event loop and returns a coroutine.
        """
        fn_update_task = partial(self.update_task, updated_task)
        return self.hass.async_add_job(fn_update_task)

    def clear_completed(self):
        """Clear completed tasks."""
        raise NotImplementedError()

    def async_clear_completed(self):
        """Clear completed.

        This method must be run in the event loop and returns a coroutine.
        """
        fn_clear_completed = self.clear_completed
        return self.hass.async_add_job(fn_clear_completed)