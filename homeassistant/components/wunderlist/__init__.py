"""Support to interact with Wunderlist."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.const import (
    CONF_NAME, CONF_ACCESS_TOKEN, CONF_TYPE)
from homeassistant.components import websocket_api

REQUIREMENTS = ['wunderpy2==0.1.6']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'wunderlist'
CONF_CLIENT_ID = 'client_id'
CONF_LIST_NAME = 'list_name'
CONF_LIST_ID = 'list_id'
CONF_TASK_ID = 'task_id'
CONF_STARRED = 'starred'
CONF_COMPLETED = 'completed'
CONF_TITLE = 'title'
CONF_TASK = 'task'
CONF_SHOW_COMPLETED = 'show_completed'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_CREATE_TASK = 'create_task'

SERVICE_SCHEMA_CREATE_TASK = vol.Schema({
    vol.Required(CONF_LIST_NAME): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_STARRED): cv.boolean,
})

WS_TYPE_LIST_TASKS = 'wunderlist/tasks/list'

SCHEMA_WEBSOCKET_LIST_TASKS = \
    websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
        vol.Required(CONF_TYPE): WS_TYPE_LIST_TASKS,
        vol.Required(CONF_LIST_ID): cv.string,
        vol.Optional(CONF_SHOW_COMPLETED): cv.boolean,
    })

WS_TYPE_ADD_TASK = 'wunderlist/tasks/add'

SCHEMA_WEBSOCKET_ADD_TASK = \
    websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
        vol.Required(CONF_TYPE): WS_TYPE_ADD_TASK,
        vol.Required(CONF_LIST_ID): cv.string,
        vol.Required(CONF_TASK): vol.Schema({
            vol.Required(CONF_TITLE): cv.string,
            vol.Optional(CONF_COMPLETED): cv.boolean,
            vol.Optional(CONF_STARRED): cv.boolean
        }, extra=vol.ALLOW_EXTRA)
    })

WS_TYPE_UPDATE_TASK = 'wunderlist/tasks/update'

SCHEMA_WEBSOCKET_UPDATE_TASK = \
    websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
        vol.Required(CONF_TYPE): WS_TYPE_UPDATE_TASK,
        vol.Required(CONF_TASK_ID): cv.string,
        vol.Required(CONF_TASK): vol.Schema({
            vol.Optional(CONF_TITLE): cv.string,
            vol.Optional(CONF_COMPLETED): cv.boolean,
            vol.Optional(CONF_STARRED): cv.boolean
        }, extra=vol.ALLOW_EXTRA)
    })


def setup(hass, config):
    """Set up the Wunderlist component."""
    conf = config[DOMAIN]
    client_id = conf.get(CONF_CLIENT_ID)
    access_token = conf.get(CONF_ACCESS_TOKEN)
    data = Wunderlist(access_token, client_id)
    if not data.check_credentials():
        _LOGGER.error("Invalid credentials")
        return False

    @callback
    def service_create_task(hass, call):
        title = call.data.get(CONF_NAME)
        completed = call.data.get(CONF_COMPLETED)
        starred = call.data.get(CONF_STARRED)
        task = {
            'title': title,
            'completed': completed,
            'starred': starred,
        }
        list_name = call.data.get(CONF_LIST_NAME)
        list = data._list_by_name(list_name)
        list_id = list["id"]
        data.add_task(list_id, task)

    hass.services.register(DOMAIN, 'create_task', service_create_task)

    @callback
    def websocket_list_tasks(hass, connection, msg):
        """Handle list tasks WS call."""
        list_id = msg.get(CONF_LIST_ID)
        show_completed = msg.get('show_completed')
        list_tasks = data.list_tasks(list_id, show_completed)
        connection.send_message(websocket_api.result_message(
            msg['id'], list_tasks))

    hass.components.websocket_api.async_register_command(
        WS_TYPE_LIST_TASKS,
        websocket_list_tasks,
        SCHEMA_WEBSOCKET_LIST_TASKS)

    @callback
    def websocket_add_task(hass, connection, msg):
        """Handle list tasks WS call."""
        list_id = msg.get(CONF_LIST_ID)
        task = msg.get(CONF_TASK)
        added_task = data.add_task(list_id, task)
        connection.send_message(websocket_api.result_message(
            msg['id'], added_task))

    hass.components.websocket_api.async_register_command(
        WS_TYPE_ADD_TASK,
        websocket_add_task,
        SCHEMA_WEBSOCKET_ADD_TASK)

    @callback
    def websocket_update_task(hass, connection, msg):
        """Handle list tasks WS call."""
        task_id = msg.get(CONF_TASK_ID)
        task = msg.get(CONF_TASK)
        updated_task = data.update_task(task_id, task)
        connection.send_message(websocket_api.result_message(
            msg['id'], updated_task))

    hass.components.websocket_api.async_register_command(
        WS_TYPE_UPDATE_TASK,
        websocket_update_task,
        SCHEMA_WEBSOCKET_UPDATE_TASK)

    return True


class Wunderlist:
    """Representation of an interface to Wunderlist."""

    def __init__(self, access_token, client_id):
        """Create new instance of Wunderlist component."""
        import wunderpy2

        api = wunderpy2.WunderApi()
        self._client = api.get_client(access_token, client_id)

        _LOGGER.debug("Instance created")

    def check_credentials(self):
        """Check if the provided credentials are valid."""
        try:
            self._client.get_lists()
            return True
        except ValueError:
            return False

    def _list_by_name(self, name):
        """Return a list ID by name."""
        lists = self._client.get_lists()
        tmp = [l for l in lists if l["title"] == name]
        if tmp:
            return tmp[0]
        return None

    def _fetch_tasks(self, list_id, show_completed):
        """Return the tasks of a list, unordered."""
        incomplete_tasks = self._client.get_tasks(list_id, False)
        if show_completed is True:
            complete_tasks = self._client.get_tasks(list_id, True)
            return incomplete_tasks + complete_tasks
        return incomplete_tasks

    def _fetch_task_order(self, list_id):
        """Return the order object of tasks in a list."""
        order_obj = self._client.get_task_positions_objs(list_id)
        order = order_obj[0].get('values')
        return order

    def _order_tasks(self, tasks, order):
        """Order tasks"""
        # https://developer.wunderlist.com/documentation/endpoints/positions
        ordered_tasks = []

        # if task is found in the order list, append it to the result
        for task_id in order:
            found_task = [t for t in tasks if str(t["id"]) == str(task_id)]
            if found_task:
                ordered_tasks.append(found_task[0])
                tasks.remove(found_task[0])

        # append all the remaining unordered tasks to the end
        if len(tasks) > 0:
            tasks.sort(key=lambda x: x["id"])
            ordered_tasks = ordered_tasks + tasks

        return ordered_tasks

    def list_tasks(self, list_id, show_completed=True):
        """Return the tasks of a list, ordered."""
        tasks = self._fetch_tasks(list_id, show_completed)
        order = self._fetch_task_order(list_id)
        ordered_tasks = self._order_tasks(tasks, order)
        return ordered_tasks

    def _fetch_task(self, task_id):
        """Get a task by id."""
        task = self._client.get_task(
            task_id=task_id)
        return task

    def update_task(self, task_id, task):
        """Update a task by id."""
        existing_task = self._fetch_task(task_id)
        # define which revision of the object we would like to edit
        rev = existing_task.get("revision", 1)
        updated_task = self._client.update_task(
            task_id=task_id,
            revision=rev,
            title=task.get(CONF_TITLE),
            completed=task.get(CONF_COMPLETED))
        return updated_task

    def add_task(self, list_id, task):
        """Add a new task to a list."""
        added_task = self._client.create_task(
            list_id=list_id,
            title=task.get(CONF_TITLE),
            starred=task.get(CONF_STARRED))
        return added_task
